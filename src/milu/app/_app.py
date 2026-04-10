# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,unused-argument
import mimetypes
import os
import time
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urljoin

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from agentscope_runtime.engine.app import AgentApp
from markdown_it import MarkdownIt

from ..config import load_config  # pylint: disable=no-name-in-module
from ..config.utils import get_config_path
from ..constant import (
    DOCS_ENABLED,
    LOG_LEVEL_ENV,
    CORS_ORIGINS,
    WORKING_DIR,
    milu_docs_zh_all_docx_path,
    milu_docs_zh_all_markdown_path,
)
from ..__version__ import __version__
from ..utils.logging import setup_logger, add_milu_file_handler
from .auth import AuthMiddleware
from .routers import router as api_router, create_agent_scoped_router
from .routers.agent_scoped import AgentContextMiddleware
from .routers.voice import voice_router
from ..envs import load_envs_into_environ
from ..providers.provider_manager import ProviderManager
from ..local_models.manager import LocalModelManager
from .multi_agent_manager import MultiAgentManager
from .migration import (
    migrate_legacy_workspace_to_default_agent,
    migrate_legacy_skills_to_skill_pool,
    ensure_default_agent_exists,
    ensure_qa_agent_exists,
)
from .channels.registry import register_custom_channel_routes

# Apply log level on load so reload child process gets same level as CLI.
logger = setup_logger(os.environ.get(LOG_LEVEL_ENV, "info"))


# Ensure static assets are served with browser-compatible MIME types across
# platforms (notably Windows may miss .js/.mjs mappings).
mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/wasm", ".wasm")

# Load persisted env vars into os.environ at module import time
# so they are available before the lifespan starts.
load_envs_into_environ()


# Dynamic runner that selects the correct workspace runner based on request
class DynamicMultiAgentRunner:
    """Runner wrapper that dynamically routes to the correct workspace runner.

    This allows AgentApp to work with multiple agents by inspecting
    the X-Agent-Id header on each request.
    """

    def __init__(self):
        self.framework_type = "agentscope"
        self._multi_agent_manager = None

    def set_multi_agent_manager(self, manager):
        """Set the MultiAgentManager instance after initialization."""
        self._multi_agent_manager = manager

    async def _get_workspace_runner(self, request):
        """Get the correct workspace runner based on request."""
        from .agent_context import get_current_agent_id

        # Get agent_id from context (set by middleware or header)
        agent_id = get_current_agent_id()

        logger.debug(f"_get_workspace_runner: agent_id={agent_id}")

        # Get the correct workspace runner
        if not self._multi_agent_manager:
            raise RuntimeError("MultiAgentManager not initialized")

        try:
            workspace = await self._multi_agent_manager.get_agent(agent_id)
            logger.debug(
                "Got workspace: %s, runner: %s",
                workspace.agent_id,
                workspace.runner,
            )
            return workspace.runner
        except ValueError as e:
            logger.error(f"Agent not found: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Error getting workspace runner: {e}",
                exc_info=True,
            )
            raise

    async def stream_query(self, request, *args, **kwargs):
        """Dynamically route to the correct workspace runner."""
        logger.debug("DynamicMultiAgentRunner.stream_query called")
        try:
            runner = await self._get_workspace_runner(request)
            logger.debug(f"Got runner: {runner}, type: {type(runner)}")
            # Delegate to the actual runner's stream_query generator
            count = 0
            async for item in runner.stream_query(request, *args, **kwargs):
                count += 1
                logger.debug(f"Yielding item #{count}: {type(item)}")
                yield item
            logger.debug(f"stream_query completed, yielded {count} items")
        except Exception as e:
            logger.error(
                f"Error in stream_query: {e}",
                exc_info=True,
            )
            # Yield error message to client
            yield {
                "error": str(e),
                "type": "error",
            }

    async def query_handler(self, request, *args, **kwargs):
        """Dynamically route to the correct workspace runner."""
        runner = await self._get_workspace_runner(request)
        # Delegate to the actual runner's query_handler generator
        async for item in runner.query_handler(request, *args, **kwargs):
            yield item

    # Async context manager support for AgentApp lifecycle
    async def __aenter__(self):
        """
        No-op context manager entry (workspaces manage their own runners).
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No-op context manager exit (workspaces manage their own runners)."""
        return None


# Use dynamic runner for AgentApp
runner = DynamicMultiAgentRunner()

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant with background task support",
    runner=runner,
    enable_stream_task=True,
    stream_task_queue="stream_query",
    stream_task_timeout=300,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):  # pylint: disable=too-many-statements,too-many-branches
    startup_start_time = time.time()
    add_milu_file_handler(WORKING_DIR / "milu.log")

    # Auto-register admin from env vars (for automated deployments)
    from .auth import auto_register_from_env

    auto_register_from_env()

    try:
        from ..utils.telemetry import (
            collect_and_upload_telemetry,
            has_telemetry_been_collected,
            is_telemetry_opted_out,
        )

        if not is_telemetry_opted_out(
            WORKING_DIR,
        ) and not has_telemetry_been_collected(WORKING_DIR):
            collect_and_upload_telemetry(WORKING_DIR)
    except Exception:
        logger.debug(
            "Telemetry collection skipped due to error",
            exc_info=True,
        )

    # --- Multi-agent migration and initialization ---
    logger.info("Checking for legacy config migration...")
    migrate_legacy_workspace_to_default_agent()
    ensure_default_agent_exists()
    migrate_legacy_skills_to_skill_pool()
    ensure_qa_agent_exists()

    # --- Multi-agent manager initialization ---
    logger.info("Initializing MultiAgentManager...")
    multi_agent_manager = MultiAgentManager()

    # Start all configured agents (handled by manager)
    await multi_agent_manager.start_all_configured_agents()

    # --- Model provider manager (non-reloadable, in-memory) ---
    provider_manager = ProviderManager.get_instance()

    # --- Local model manager initialization ---
    local_model_manager = LocalModelManager.get_instance()

    # Expose to endpoints - multi-agent manager
    app.state.multi_agent_manager = multi_agent_manager

    # Connect DynamicMultiAgentRunner to MultiAgentManager
    if isinstance(runner, DynamicMultiAgentRunner):
        runner.set_multi_agent_manager(multi_agent_manager)

    # Helper function to get agent instance by ID (async)
    async def _get_agent_by_id(agent_id: str = None):
        """Get agent instance by ID, or active agent if not specified."""
        if agent_id is None:
            config = load_config(get_config_path())
            agent_id = config.agents.active_agent or "default"
        return await multi_agent_manager.get_agent(agent_id)

    app.state.get_agent_by_id = _get_agent_by_id

    # Global managers (shared across all agents)
    app.state.provider_manager = provider_manager
    app.state.local_model_manager = local_model_manager

    provider_manager.start_local_model_resume(local_model_manager)

    # Setup approval service with default agent's channel_manager
    default_agent = await multi_agent_manager.get_agent("default")
    if default_agent.channel_manager:
        from .approvals import get_approval_service

        get_approval_service().set_channel_manager(
            default_agent.channel_manager,
        )

    startup_elapsed = time.time() - startup_start_time
    logger.debug(
        f"Application startup completed in {startup_elapsed:.3f} seconds",
    )

    try:
        yield
    finally:
        local_model_mgr = getattr(app.state, "local_model_manager", None)
        if local_model_mgr is not None:
            logger.info("Stopping local model server...")
            try:
                await local_model_mgr.shutdown_server()
            except Exception as exc:
                logger.error(
                    "Error shutting down local model server gracefully: %s",
                    exc,
                )
                with suppress(OSError, RuntimeError, ValueError):
                    local_model_mgr.force_shutdown_server()

        # Stop multi-agent manager (stops all agents and their components)
        multi_agent_mgr = getattr(app.state, "multi_agent_manager", None)
        if multi_agent_mgr is not None:
            logger.info("Stopping MultiAgentManager...")
            try:
                await multi_agent_mgr.stop_all()
            except Exception as e:
                logger.error(f"Error stopping MultiAgentManager: {e}")

        logger.info("Application shutdown complete")


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)

# Add agent context middleware for agent-scoped routes
app.add_middleware(AgentContextMiddleware)

app.add_middleware(AuthMiddleware)

# Apply CORS middleware if CORS_ORIGINS is set
if CORS_ORIGINS:
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )


# Console static dir: env, or milu package data (console), or cwd.
_CONSOLE_STATIC_ENV = "milu_CONSOLE_STATIC_DIR"


def _resolve_console_static_dir() -> str:
    if os.environ.get(_CONSOLE_STATIC_ENV):
        return os.environ[_CONSOLE_STATIC_ENV]
    # In source checkouts, prefer the freshly built frontend dist over the
    # packaged copy under src/milu/console so backend-served assets stay in
    # sync with the latest console build.
    pkg_dir = Path(__file__).resolve().parent.parent
    repo_dir = pkg_dir.parent.parent
    candidate = repo_dir / "console" / "dist"
    if candidate.is_dir() and (candidate / "index.html").exists():
        return str(candidate)

    # Shipped dist lives in milu package as static data.
    candidate = pkg_dir / "console"
    if candidate.is_dir() and (candidate / "index.html").exists():
        return str(candidate)

    # Fallback to cwd data
    cwd = Path(os.getcwd())
    for subdir in ("console/dist", "console_dist"):
        candidate = cwd / subdir
        if candidate.is_dir() and (candidate / "index.html").exists():
            return str(candidate)

    fallback = cwd / "console" / "dist"
    logger.warning(
        f"Console static directory not found. Falling back to '{fallback}'.",
    )
    return str(fallback)


_CONSOLE_STATIC_DIR = _resolve_console_static_dir()
_CONSOLE_INDEX = (
    Path(_CONSOLE_STATIC_DIR) / "index.html" if _CONSOLE_STATIC_DIR else None
)
logger.info(f"STATIC_DIR: {_CONSOLE_STATIC_DIR}")


@app.get("/")
def read_root():
    if _CONSOLE_INDEX and _CONSOLE_INDEX.exists():
        return FileResponse(_CONSOLE_INDEX)
    return {
        "message": (
            "milu Web Console is not available. "
            "If you installed milu from source code, please run "
            "`npm ci && npm run build` in milu's `console/` "
            "directory, and restart milu to enable the "
            "web console."
        ),
    }


@app.get("/api/version")
def get_version():
    """Return the current milu version."""
    return {"version": __version__}


@app.get("/api/healthz")
def healthz():
    """Lightweight readiness probe for local startup scripts."""
    return {"status": "ok", "version": __version__}


app.include_router(api_router, prefix="/api")

# Agent-scoped router: /api/agents/{agentId}/chats, etc.
agent_scoped_router = create_agent_scoped_router()
app.include_router(agent_scoped_router, prefix="/api")


app.include_router(
    agent_app.router,
    prefix="/api/agent",
    tags=["agent"],
)

# Voice channel: Twilio-facing endpoints at root level (not under /api/).
# POST /voice/incoming, WS /voice/ws, POST /voice/status-callback
app.include_router(voice_router, tags=["voice"])

# Custom channel routes (before SPA catch-all to ensure route priority)
register_custom_channel_routes(app)

_DOCX_MEDIA = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_DOCS_ASSETS_ROUTE = "/milu-docs-zh-assets"
_docs_markdown_dir = milu_docs_zh_all_markdown_path().parent
if _docs_markdown_dir.is_dir():
    app.mount(
        _DOCS_ASSETS_ROUTE,
        StaticFiles(directory=str(_docs_markdown_dir)),
        name="milu_docs_zh_assets",
    )

_DOCS_MARKDOWN_RENDERER = MarkdownIt(
    "commonmark",
    {"html": True, "linkify": True},
).enable("table").enable("strikethrough")


def _slugify_docs_heading(text: str, fallback: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", normalized)
    normalized = re.sub(r"[-\s]+", "-", normalized).strip("-")
    return normalized or fallback


def _extract_docs_toc(markdown_text: str) -> list[dict[str, object]]:
    """Extract a grouped TOC that mirrors the reference site layout.

    The markdown starts with overview categories (## 欢迎, ## 控制, ...),
    each containing ``- [Title](#anchor)`` items.  These are parsed into
    groups; each item links to the anchor ID embedded in the markdown.
    """
    toc: list[dict[str, object]] = []
    current_group: dict[str, object] | None = None
    in_overview = True
    link_pattern = re.compile(r"- \[(.+?)]\(#(.+?)\)")

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            title = line[3:].strip()
            if title == "项目介绍":
                in_overview = False
                break
            if in_overview:
                current_group = {
                    "category": title,
                    "children": [],
                }
                toc.append(current_group)
                continue

        if in_overview and current_group is not None:
            m = link_pattern.match(line)
            if m:
                current_group["children"].append(
                    {"title": m.group(1), "id": m.group(2)},
                )

    return toc


def _inject_docs_heading_ids(
    rendered_html: str,
    heading_entries: list[tuple[str, str]],
) -> str:
    if not heading_entries:
        return rendered_html

    entry_iter = iter(heading_entries)

    def _replacer(match: re.Match[str]) -> str:
        try:
            heading_tag, heading_id = next(entry_iter)
        except StopIteration:
            return match.group(0)
        return f"<{heading_tag} id=\"{heading_id}\" class=\"docs-heading\">"

    pattern = re.compile(r"<(h[23])>")
    return pattern.sub(_replacer, rendered_html, count=len(heading_entries))


def _rebrand_docs_text(markdown_text: str) -> str:
    """Replace CoPaw branding with MiLu in documentation text.

    Preserves external URLs (copaw.agentscope.io, github.com/...CoPaw,
    Docker images, etc.) while renaming the product name and CLI commands.
    """
    _URL_PLACEHOLDER = "\x00URL\x00"
    urls: list[str] = []

    def _save_url(m: re.Match[str]) -> str:
        urls.append(m.group(0))
        return f"{_URL_PLACEHOLDER}{len(urls) - 1}{_URL_PLACEHOLDER}"

    protected = re.sub(
        r"https?://[^\s\)\]\>\"\']+", _save_url, markdown_text,
    )
    protected = (
        protected
        .replace("CoPaw-Flash", "MiLu-Flash")
        .replace("CoPaw", "MiLu")
        .replace("copaw", "milu")
    )

    def _restore_url(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        return urls[idx]

    return re.sub(
        rf"{re.escape(_URL_PLACEHOLDER)}(\d+){re.escape(_URL_PLACEHOLDER)}",
        _restore_url,
        protected,
    )


def _rewrite_docs_asset_links(rendered_html: str) -> str:
    rendered_html = re.sub(
        r'href="(?!https?://|mailto:|#|/)([^"]+)"',
        lambda m: f'href="{urljoin(_DOCS_ASSETS_ROUTE + "/", m.group(1))}"',
        rendered_html,
    )
    rendered_html = re.sub(
        r'src="(?!https?://|data:|/)([^"]+)"',
        lambda m: f'src="{urljoin(_DOCS_ASSETS_ROUTE + "/", m.group(1))}"',
        rendered_html,
    )
    rendered_html = re.sub(
        r"<img(?![^>]*\bloading=)([^>]*)>",
        r'<img loading="lazy" decoding="async"\1>',
        rendered_html,
    )
    return rendered_html


def _render_docs_sections(
    markdown_text: str,
    toc: list[dict[str, object]],
) -> str:
    # Move ``<a id="...">`` anchors to after the heading so they land
    # in the same visible section after splitting.
    markdown_text = re.sub(
        r'^(<a\s+id="([^"]+)"\s*>\s*</a>)\s*\n+(## .+)',
        r"\3\n\1",
        markdown_text,
        flags=re.MULTILINE,
    )
    # Collect all anchor IDs → heading-title mapping for ID injection
    anchor_by_title: dict[str, str] = {}
    for m in re.finditer(
        r'^(## .+?)\s*\n\s*<a\s+id="([^"]+)"',
        markdown_text,
        flags=re.MULTILINE,
    ):
        title = m.group(1)[3:].strip()
        anchor_by_title[title] = m.group(2)

    parts = re.split(r"(?=^##\s+)", markdown_text, flags=re.MULTILINE)
    sections: list[str] = []
    main_content_started = False
    for index, part in enumerate(parts):
        stripped = part.strip()
        if not stripped:
            continue
        rendered = _DOCS_MARKDOWN_RENDERER.render(stripped)
        section_title = ""
        if index > 0:
            lines = stripped.splitlines()
            if lines:
                section_title = (
                    lines[0][3:].strip() if lines[0].startswith("## ") else ""
                )
                anchor_id = anchor_by_title.get(section_title)
                if anchor_id:
                    rendered = re.sub(
                        r"<h2>",
                        f'<h2 id="{anchor_id}" class="docs-heading">',
                        rendered,
                        count=1,
                    )
        rendered = _rewrite_docs_asset_links(rendered)
        if section_title == "项目介绍":
            main_content_started = True

        if index == 0:
            css_class = "docs-section docs-section-intro"
        elif not main_content_started:
            css_class = "docs-section docs-section-overview"
        else:
            css_class = "docs-section"
        sections.append(f"<section class='{css_class}'>{rendered}</section>")
    return "".join(sections)


def _docs_content_version() -> int:
    md_path = milu_docs_zh_all_markdown_path()
    versions = [md_path.stat().st_mtime_ns] if md_path.is_file() else []
    image_dir = _docs_markdown_dir / "images"
    if image_dir.is_dir():
        for p in image_dir.rglob("*"):
            if p.is_file():
                versions.append(p.stat().st_mtime_ns)
    return max(versions) if versions else 0


@app.get("/milu-docs-zh-all.docx")
def _serve_milu_docs_zh_all():
    """Serve in-repo Chinese documentation (see ``milu_DOCS_ZH_ALL_DOCX_RELPATH``)."""
    f = milu_docs_zh_all_docx_path()
    if f.is_file():
        return FileResponse(
            f,
            media_type=_DOCX_MEDIA,
            filename="milu-docs-zh-all.docx",
        )
    raise HTTPException(status_code=404, detail="Documentation file not found")


@app.get("/milu-docs-zh", response_class=HTMLResponse)
def _render_milu_docs_zh():
    """Render local Chinese docs as an in-browser HTML page."""
    f = milu_docs_zh_all_markdown_path()
    if not f.is_file():
        raise HTTPException(status_code=404, detail="Documentation file not found")
    text = f.read_text(encoding="utf-8", errors="replace")
    text = _rebrand_docs_text(text)
    toc = _extract_docs_toc(text)
    rendered = _render_docs_sections(text, toc)
    toc_html = "".join(
        (
            "<li class='docs-toc-group'>"
            f"<span class='docs-toc-group-title'>{group['category']}</span>"
            "<ul class='docs-toc-sublist'>"
            + "".join(
                f"<li class='docs-toc-item'><a href='#{child['id']}' class='docs-toc-link'>{child['title']}</a></li>"
                for child in group["children"]
            )
            + "</ul></li>"
        )
        for group in toc
    )
    version = _docs_content_version()
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
            "<title>MiLu</title>"
            "<style>:root{color-scheme:light}"
            "html{scroll-behavior:auto}"
            "body{max-width:1400px;margin:24px auto;padding:0 20px;"
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;"
            "line-height:1.7;color:#222;background:#fff}"
            ".docs-layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:40px;align-items:start}"
            ".docs-sidebar{position:sticky;top:20px;max-height:calc(100vh - 40px);overflow:auto;"
            "padding:20px 16px;border-right:1px solid #e5e7eb;background:#fff}"
            ".docs-sidebar-title{margin:0 0 16px;font-size:13px;font-weight:700;color:#888;"
            "text-transform:uppercase;letter-spacing:.06em}"
            ".docs-toc{list-style:none;padding:0;margin:0}"
            ".docs-toc-group{margin:0 0 18px}"
            ".docs-toc-group-title{display:block;font-size:12px;font-weight:700;color:#999;"
            "text-transform:uppercase;letter-spacing:.05em;padding:0 8px 4px;margin-bottom:4px}"
            ".docs-toc-item{margin:0}"
            ".docs-toc-link{display:block;color:#4a5568;text-decoration:none;font-size:14px;font-weight:500;"
            "padding:5px 8px;border-radius:6px;border-left:3px solid transparent;"
            "transition:color .15s,background .15s,border-color .15s}"
            ".docs-toc-link:hover{color:#2f5fd7;background:#f0f4ff}"
            ".docs-toc-link-active{color:#1f4ed8;background:#eaf1ff;border-left-color:#3b82f6;font-weight:600}"
            ".docs-toc-sublist{list-style:none;padding:0;margin:0}"
            ".docs-main{min-width:0;padding-bottom:48px}"
            ".docs-mobile-toc{display:none;margin:0 0 20px;padding:12px 14px;border:1px solid #e5e7eb;"
            "border-radius:12px;background:#fafafa}"
            ".docs-mobile-toc summary{cursor:pointer;font-weight:600}"
            ".docs-mobile-toc .docs-toc{margin-top:10px}"
            ".docs-section{margin:0 0 28px;content-visibility:auto;contain-intrinsic-size:auto 500px}"
            ".docs-section-intro{display:none}"
            ".docs-section-overview{display:none}"
            ".docs-heading{scroll-margin-top:24px}"
            "h2{font-size:1.6em;border-bottom:1px solid #eaecef;padding-bottom:.3em;margin-top:1.5em}"
            "h3{font-size:1.3em;margin-top:1.3em}"
            "img{max-width:100%;height:auto;display:block;margin:14px 0}"
            "a{color:#2f5fd7;text-decoration:none}a:hover{text-decoration:underline}"
            "code{background:#f4f4f4;padding:2px 5px;border-radius:4px;font-size:.9em}"
            "pre{background:#f6f8fa;padding:16px;border-radius:8px;overflow:auto;font-size:.9em}"
            "pre code{background:none;padding:0}"
            "table{border-collapse:collapse;width:auto;margin:16px 0;font-size:.95em}"
            "thead{background:#f6f8fa}"
            "th{font-weight:600;text-align:left;padding:10px 16px;border:1px solid #d0d7de}"
            "td{padding:10px 16px;border:1px solid #d0d7de}"
            "tr:nth-child(even){background:#fafbfc}"
            "blockquote{border-left:4px solid #dfe2e5;margin:16px 0;padding:0 16px;color:#6a737d}"
            "@media (max-width: 980px){.docs-layout{grid-template-columns:1fr}"
            ".docs-sidebar{display:none}.docs-mobile-toc{display:block}}"
            "</style></head><body>"
            "<div class='docs-layout'>"
            "<aside class='docs-sidebar'>"
            "<h2 class='docs-sidebar-title'>MiLu 文档</h2>"
            f"<ul class='docs-toc'>{toc_html}</ul>"
            "</aside>"
            "<main class='docs-main' data-docs-version='"
            f"{version}"
            "'>"
            "<details class='docs-mobile-toc'><summary>目录</summary>"
            f"<ul class='docs-toc'>{toc_html}</ul>"
            "</details>"
            + rendered
            + "</main></div>"
            "<script>"
            "(function(){"
            "var links=[].slice.call(document.querySelectorAll('.docs-toc-link'));"
            "var byId={};"
            "links.forEach(function(a){var h=a.getAttribute('href')||'';if(h[0]==='#')byId[h.slice(1)]=a;});"
            "var prev=null;"
            "function setActive(id){"
            "if(prev)prev.classList.remove('docs-toc-link-active');"
            "var a=byId[id];if(a){a.classList.add('docs-toc-link-active');a.scrollIntoView({block:'nearest',behavior:'auto'});prev=a;}}"
            # Scroll-spy: throttled scroll listener (much cheaper than 161 observers)
            "var headings=[].slice.call(document.querySelectorAll('h2.docs-heading'));"
            "var cur=headings.length?headings[0].id:'';"
            "var clickLock=0;"  # suppress scroll-spy briefly after TOC click
            "var rafId=0;"
            "function spy(){"
            "if(clickLock)return;"
            "var top=window.scrollY||document.documentElement.scrollTop;"
            "var best='';"
            "for(var i=headings.length-1;i>=0;i--){"
            "if(headings[i].offsetTop<=top+80){best=headings[i].id;break;}}"
            "if(!best&&headings.length)best=headings[0].id;"
            "if(best&&best!==cur){cur=best;setActive(cur);}}"
            "window.addEventListener('scroll',function(){if(!rafId)rafId=requestAnimationFrame(function(){rafId=0;spy();});},{passive:true});"
            # TOC link click: instant jump + lock observer
            "links.forEach(function(a){"
            "a.addEventListener('click',function(e){"
            "e.preventDefault();"
            "var id=a.getAttribute('href').slice(1);"
            "var el=document.getElementById(id);"
            "if(!el)return;"
            "clickLock=1;cur=id;setActive(id);"
            "el.scrollIntoView({block:'start',behavior:'auto'});"
            "setTimeout(function(){clickLock=0;},150);"
            "history.replaceState(null,'','#'+id);"
            "});});"
            # Init
            "if(location.hash)cur=location.hash.slice(1);"
            "setActive(cur);"
            "spy();"
            "})();"
            "</script>"
            "</body></html>"
        )
    )


@app.get("/milu-docs-zh-meta")
def _milu_docs_zh_meta():
    version = _docs_content_version()
    return {"version": version}

# Console static files and SPA fallback
# Register these AFTER API routes to ensure proper routing priority
if os.path.isdir(_CONSOLE_STATIC_DIR):
    _console_path = Path(_CONSOLE_STATIC_DIR)
    _LOGO_CACHE_HEADERS = {"Cache-Control": "public, max-age=0, must-revalidate"}

    def _serve_console_index():
        if _CONSOLE_INDEX and _CONSOLE_INDEX.exists():
            return FileResponse(_CONSOLE_INDEX)

        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/logo.png")
    def _console_logo():
        f = _console_path / "logo.png"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/png",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/dark-logo.png")
    def _console_dark_logo():
        f = _console_path / "dark-logo.png"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/png",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/milu-logo.png")
    def _console_milu_favicon():
        f = _console_path / "milu-logo.png"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/png",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/milu-favicon.png")
    def _console_milu_tab_favicon():
        """Tab icon: scaled raster from milu-logo (sync script); distinct URL vs milu-logo.png for cache bust."""
        f = _console_path / "milu-favicon.png"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/png",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/favicon.ico")
    def _favicon_ico():
        """Serve PNG bytes (not redirect) so clients do not pin an old redirect target."""
        for name in ("milu-favicon.png", "milu-logo.png"):
            f = _console_path / name
            if f.is_file():
                return FileResponse(
                    f,
                    media_type="image/png",
                    headers=_LOGO_CACHE_HEADERS,
                )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/milu-symbol.svg")
    def _console_icon():
        f = _console_path / "milu-symbol.svg"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/svg+xml",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/milu-dark.png")
    def _console_dark_icon():
        f = _console_path / "milu-dark.png"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/png",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/milu-local-288.png")
    def _console_milu_local_avatar():
        f = _console_path / "milu-local-288.png"
        if f.is_file():
            return FileResponse(
                f,
                media_type="image/png",
                headers=_LOGO_CACHE_HEADERS,
            )
        raise HTTPException(status_code=404, detail="Not Found")

    _assets_dir = _console_path / "assets"
    if _assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_assets_dir)),
            name="assets",
        )

    @app.get("/console")
    @app.get("/console/")
    @app.get("/console/{full_path:path}")
    def _console_spa_alias(full_path: str = ""):
        _ = full_path
        return _serve_console_index()

    # SPA fallback: catch-all route for frontend routing
    # Must be registered AFTER all API routes to avoid conflicts
    @app.get("/{full_path:path}")
    def _console_spa(full_path: str):
        # Prevent catching common system/special paths
        if full_path in ("docs", "redoc", "openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")
        # Skip API routes (should already be matched due to registration order)
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        return _serve_console_index()
