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
    # packaged copy under src/copaw/console so backend-served assets stay in
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
)


def _slugify_docs_heading(text: str, fallback: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", normalized)
    normalized = re.sub(r"[-\s]+", "-", normalized).strip("-")
    return normalized or fallback


def _extract_docs_toc(markdown_text: str) -> list[dict[str, object]]:
    toc: list[dict[str, object]] = []
    current_section: dict[str, object] | None = None
    section_index = 0
    subsection_index = 0
    main_content_started = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            title = line[3:].strip()
            if title == "项目介绍":
                main_content_started = True
            if not main_content_started:
                current_section = None
                continue

            section_index += 1
            subsection_index = 0
            current_section = {
                "id": _slugify_docs_heading(title, f"section-{section_index}"),
                "title": title,
                "children": [],
            }
            toc.append(current_section)
            continue

        if line.startswith("### ") and current_section is not None:
            subsection_index += 1
            title = line[4:].strip()
            child = {
                "id": _slugify_docs_heading(
                    title,
                    f"{current_section['id']}-sub-{subsection_index}",
                ),
                "title": title,
            }
            current_section["children"].append(child)

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
    toc_by_title = {
        str(section["title"]): section
        for section in toc
    }
    parts = re.split(r"(?=^##\s+)", markdown_text, flags=re.MULTILINE)
    sections: list[str] = []
    main_content_started = False
    for index, part in enumerate(parts):
        stripped = part.strip()
        if not stripped:
            continue
        rendered = _DOCS_MARKDOWN_RENDERER.render(stripped)
        heading_entries: list[tuple[str, str]] = []
        section_title = ""
        if index > 0:
            lines = stripped.splitlines()
            if lines:
                section_title = (
                    lines[0][3:].strip() if lines[0].startswith("## ") else ""
                )
                section_meta = toc_by_title.get(section_title)
                if section_meta is not None:
                    heading_entries.append(("h2", str(section_meta["id"])))
                    for child in section_meta["children"]:
                        heading_entries.append(("h3", str(child["id"])))
        rendered = _inject_docs_heading_ids(rendered, heading_entries)
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
    toc = _extract_docs_toc(text)
    rendered = _render_docs_sections(text, toc)
    toc_html = "".join(
        (
            "<li class='docs-toc-item'>"
            f"<a href='#{section['id']}' class='docs-toc-link'>{section['title']}</a>"
            + (
                "<ul class='docs-toc-sublist'>"
                + "".join(
                    f"<li><a href='#{child['id']}' class='docs-toc-sublink'>{child['title']}</a></li>"
                    for child in section["children"]
                )
                + "</ul>"
                if section["children"]
                else ""
            )
            + "</li>"
        )
        for section in toc
    )
    version = _docs_content_version()
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
            "<title>MiLu</title>"
            "<style>:root{color-scheme:light}"
            "html{scroll-behavior:smooth}"
            "body{max-width:1400px;margin:24px auto;padding:0 20px;"
            "font-family:Arial,Helvetica,sans-serif;line-height:1.7;color:#222;"
            "background:#fff}"
            ".docs-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:32px;align-items:start}"
            ".docs-sidebar{position:sticky;top:20px;max-height:calc(100vh - 40px);overflow:auto;"
            "padding:18px 16px;border:1px solid #e5e7eb;border-radius:16px;background:#fafafa}"
            ".docs-sidebar-title{margin:0 0 12px;font-size:14px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.04em}"
            ".docs-toc{list-style:none;padding:0;margin:0}"
            ".docs-toc-item{margin:0 0 12px}"
            ".docs-toc-link,.docs-toc-sublink{display:block;color:#2d3748;text-decoration:none;transition:color .15s ease,background-color .15s ease}"
            ".docs-toc-link{font-weight:600;padding:6px 8px;border-radius:8px}"
            ".docs-toc-link:hover,.docs-toc-sublink:hover{color:#2f5fd7}"
            ".docs-toc-sublist{list-style:none;padding:6px 0 0 12px;margin:0}"
            ".docs-toc-sublist li{margin:0 0 6px}"
            ".docs-toc-sublink{font-size:14px;color:#4a5568;padding:4px 8px;border-radius:8px}"
            ".docs-toc-link-active{background:#eaf1ff;color:#1f4ed8}"
            ".docs-toc-sublink-active{background:#eef4ff;color:#1f4ed8;font-weight:600}"
            ".docs-main{min-width:0;padding-bottom:48px}"
            ".docs-mobile-toc{display:none;margin:0 0 20px;padding:12px 14px;border:1px solid #e5e7eb;border-radius:12px;background:#fafafa}"
            ".docs-mobile-toc summary{cursor:pointer;font-weight:600}"
            ".docs-mobile-toc .docs-toc{margin-top:10px}"
            ".docs-section{content-visibility:auto;contain-intrinsic-size:1200px;"
            "contain:layout style paint;margin:0 0 28px}"
            ".docs-section-intro{display:none}"
            ".docs-section-overview{display:none}"
            ".docs-heading{scroll-margin-top:24px}"
            "img{max-width:100%;height:auto;display:block;margin:14px 0}"
            "a{color:#2f5fd7;text-decoration:none}a:hover{text-decoration:underline}"
            "code{background:#f4f4f4;padding:2px 4px;border-radius:4px}"
            "pre{background:#f7f7f7;padding:12px;border-radius:8px;overflow:auto}"
            "table{border-collapse:collapse;width:100%;margin:10px 0;display:block;overflow:auto}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
            "@media (max-width: 980px){.docs-layout{grid-template-columns:1fr}.docs-sidebar{display:none}.docs-mobile-toc{display:block}}"
            "</style></head><body>"
            "<div class='docs-layout'>"
            "<aside class='docs-sidebar'>"
            "<h2 class='docs-sidebar-title'>目录</h2>"
            f"<ul class='docs-toc'>{toc_html}</ul>"
            "</aside>"
            "<main class='docs-main' data-docs-version='"
            f"{version}"
            "'>"
            "<h1>MiLu</h1>"
            "<details class='docs-mobile-toc'><summary>目录</summary>"
            f"<ul class='docs-toc'>{toc_html}</ul>"
            "</details>"
            + rendered
            + "</main></div>"
            "<script>"
            "(function(){"
            "const links=[...document.querySelectorAll('.docs-toc-link,.docs-toc-sublink')];"
            "const byId=new Map();"
            "for(const link of links){const href=link.getAttribute('href')||'';if(href.startsWith('#')){byId.set(href.slice(1),link);}}"
            "function setActive(id){"
            "for(const link of links){link.classList.remove('docs-toc-link-active','docs-toc-sublink-active');}"
            "if(!id)return;"
            "const active=byId.get(id);"
            "if(!active)return;"
            "active.classList.add(active.classList.contains('docs-toc-sublink')?'docs-toc-sublink-active':'docs-toc-link-active');"
            "const parentItem=active.closest('.docs-toc-item');"
            "if(parentItem){const parentLink=parentItem.querySelector(':scope > .docs-toc-link');if(parentLink&&parentLink!==active){parentLink.classList.add('docs-toc-link-active');}}"
            "active.scrollIntoView({block:'nearest'});"
            "}"
            "const headings=[...document.querySelectorAll('h2.docs-heading,h3.docs-heading')];"
            "let currentId=headings[0]?.id||'';"
            "if(location.hash){currentId=location.hash.slice(1);}"
            "setActive(currentId);"
            "const observer=new IntersectionObserver((entries)=>{"
            "const visible=entries.filter((entry)=>entry.isIntersecting);"
            "if(!visible.length)return;"
            "visible.sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);"
            "const nextId=visible[0].target.id;"
            "if(nextId&&nextId!==currentId){currentId=nextId;setActive(currentId);}"
            "},{rootMargin:'-15% 0px -70% 0px',threshold:[0,1]});"
            "for(const heading of headings){observer.observe(heading);}"
            "window.addEventListener('hashchange',()=>{const nextId=location.hash.slice(1);if(nextId){currentId=nextId;setActive(nextId);}});"
            "for(const link of links){link.addEventListener('click',()=>{const href=link.getAttribute('href')||'';if(href.startsWith('#')){const nextId=href.slice(1);currentId=nextId;setActive(nextId);}});}"
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
