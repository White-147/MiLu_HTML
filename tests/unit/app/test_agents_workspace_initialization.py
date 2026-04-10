# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"""Regression tests for agent workspace initialization."""

import json
from pathlib import Path
from types import SimpleNamespace

from copaw.agents.memory.agent_md_manager import AgentMdManager
from copaw.app import migration as migration_module
from copaw.app.routers import agents as agents_router
from copaw.config.config import (
    AgentProfileConfig,
    AgentProfileRef,
    AgentsConfig,
    Config,
    load_agent_config,
    save_agent_config,
)


def _stub_global_config(language: str = "en") -> SimpleNamespace:
    return SimpleNamespace(
        agents=SimpleNamespace(language=language),
    )


def _patch_test_working_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("copaw.config.utils.WORKING_DIR", tmp_path)
    monkeypatch.setattr("copaw.config.config.WORKING_DIR", tmp_path)
    monkeypatch.setattr("copaw.app.migration.WORKING_DIR", tmp_path)
    try:
        monkeypatch.setattr("milu.config.utils.WORKING_DIR", tmp_path)
        monkeypatch.setattr("milu.config.config.WORKING_DIR", tmp_path)
        monkeypatch.setattr("milu.app.migration.WORKING_DIR", tmp_path)
    except ImportError:
        pass


def _patch_package_load_config(
    monkeypatch,
    *,
    language: str,
) -> None:
    loader = lambda: _stub_global_config(language)

    import copaw.config as config_module

    monkeypatch.setattr(config_module, "load_config", loader)
    try:
        import milu.config as milu_config_module
    except ImportError:
        milu_config_module = None

    if milu_config_module is not None:
        monkeypatch.setattr(milu_config_module, "load_config", loader)


def _write_root_config(
    workspace_dir: Path,
    *,
    language: str = "zh",
) -> None:
    root_config = Config(
        agents=AgentsConfig(
            active_agent="default",
            profiles={
                "default": AgentProfileRef(
                    id="default",
                    workspace_dir=str(workspace_dir),
                ),
            },
            language=language,
        ),
    )

    config_path = tmp_path / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(root_config.model_dump(exclude_none=True)),
        encoding="utf-8",
    )


def _write_language_only_config(
    monkeypatch,
    tmp_path: Path,
    *,
    language: str,
) -> None:
    monkeypatch.setattr("copaw.config.utils.WORKING_DIR", tmp_path)
    monkeypatch.setattr("copaw.config.config.WORKING_DIR", tmp_path)
    try:
        monkeypatch.setattr("milu.config.utils.WORKING_DIR", tmp_path)
        monkeypatch.setattr("milu.config.config.WORKING_DIR", tmp_path)
    except ImportError:
        pass

    root_config = Config(
        agents=AgentsConfig(language=language),
    )
    config_path = tmp_path / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(root_config.model_dump(exclude_none=True)),
        encoding="utf-8",
    )


def _template_dir(language: str) -> Path:
    return (
        Path(agents_router.__file__).resolve().parent.parent.parent
        / "agents"
        / "md_files"
        / language
    )


def test_copy_builtin_skills_targets_unified_skills_dir(monkeypatch, tmp_path):
    """Builtin skills should seed into workspace ``skills/``."""
    copied_targets: list[Path] = []

    def _record_copytree(_source: Path, target: Path) -> None:
        copied_targets.append(target)

    monkeypatch.setattr(agents_router.shutil, "copytree", _record_copytree)

    agents_router._copy_builtin_skills(tmp_path)

    assert copied_targets
    assert all(
        target.parent == tmp_path / "skills" for target in copied_targets
    )


def test_initialize_agent_workspace_creates_runtime_compatible_files(
    monkeypatch,
    tmp_path,
):
    """New workspaces should match the runtime file contract."""
    _patch_package_load_config(monkeypatch, language="en")
    monkeypatch.setattr(agents_router, "_copy_builtin_skills", lambda _: None)
    monkeypatch.setattr(
        agents_router,
        "_install_initial_skills",
        lambda workspace_dir, skill_names: None,
    )

    agents_router._initialize_agent_workspace(tmp_path)

    assert (tmp_path / "sessions").is_dir()
    assert (tmp_path / "memory").is_dir()
    assert (tmp_path / "skills").is_dir()
    assert not (tmp_path / "active_skills").exists()
    assert not (tmp_path / "customized_skills").exists()
    assert json.loads(
        (tmp_path / "jobs.json").read_text(encoding="utf-8"),
    ) == {
        "version": 1,
        "jobs": [],
    }
    assert json.loads(
        (tmp_path / "chats.json").read_text(encoding="utf-8"),
    ) == {
        "version": 1,
        "chats": [],
    }


def test_initialize_agent_workspace_builtin_qa_seed_passes_language_first(
    monkeypatch,
    tmp_path,
):
    """Builtin QA seeding should pass language before workspace."""
    recorded_calls: list[tuple[str, Path]] = []

    _write_language_only_config(monkeypatch, tmp_path, language="ru")
    monkeypatch.setattr(
        agents_router,
        "copy_builtin_qa_md_files",
        lambda language, workspace_dir: recorded_calls.append(
            (language, Path(workspace_dir)),
        ),
    )
    monkeypatch.setattr(agents_router, "_copy_builtin_skills", lambda _: None)
    monkeypatch.setattr(
        agents_router,
        "_install_initial_skills",
        lambda workspace_dir, skill_names: None,
    )

    agents_router._initialize_agent_workspace(
        tmp_path,
        builtin_qa_md_seed=True,
    )

    assert recorded_calls == [("ru", tmp_path)]


def test_ensure_default_agent_repairs_missing_workspace_templates(
    monkeypatch,
    tmp_path,
):
    """Default workspace should self-heal missing md templates."""
    default_workspace = tmp_path / "workspaces" / "default"
    default_workspace.mkdir(parents=True, exist_ok=True)

    _patch_test_working_dir(monkeypatch, tmp_path)
    _write_root_config(default_workspace, language="zh")
    save_agent_config(
        "default",
        AgentProfileConfig(
            id="default",
            name="Default Agent",
            workspace_dir=str(default_workspace),
            language="zh",
        ),
    )
    migration_module._ensure_workspace_json_files(default_workspace)

    migration_module._do_ensure_default_agent()

    expected_files = {
        path.name for path in _template_dir("zh").glob("*.md")
    }
    actual_files = {path.name for path in default_workspace.glob("*.md")}
    listed_files = {
        item["filename"]
        for item in AgentMdManager(default_workspace).list_working_mds()
    }

    assert expected_files <= actual_files
    assert expected_files <= listed_files
    assert (default_workspace / "sessions").is_dir()
    assert (default_workspace / "memory").is_dir()
    assert (default_workspace / "skills").is_dir()


def test_ensure_default_agent_preserves_existing_workspace_templates(
    monkeypatch,
    tmp_path,
):
    """Existing md files should never be overwritten during repair."""
    default_workspace = tmp_path / "workspaces" / "default"
    default_workspace.mkdir(parents=True, exist_ok=True)

    _patch_test_working_dir(monkeypatch, tmp_path)
    _write_root_config(default_workspace, language="zh")
    save_agent_config(
        "default",
        AgentProfileConfig(
            id="default",
            name="Default Agent",
            workspace_dir=str(default_workspace),
            language="zh",
        ),
    )

    custom_agents = "# Custom AGENTS\nkeep me\n"
    custom_bootstrap = "# Custom BOOTSTRAP\nkeep me too\n"
    (default_workspace / "AGENTS.md").write_text(
        custom_agents,
        encoding="utf-8",
    )
    (default_workspace / "BOOTSTRAP.md").write_text(
        custom_bootstrap,
        encoding="utf-8",
    )

    migration_module._do_ensure_default_agent()

    assert (
        default_workspace / "AGENTS.md"
    ).read_text(encoding="utf-8") == custom_agents
    assert (
        default_workspace / "BOOTSTRAP.md"
    ).read_text(encoding="utf-8") == custom_bootstrap
    assert {
        path.name for path in _template_dir("zh").glob("*.md")
    } <= {
        path.name for path in default_workspace.glob("*.md")
    }


def test_ensure_default_agent_uses_global_language_when_agent_json_missing(
    monkeypatch,
    tmp_path,
):
    """Fallback language should come from root config when agent.json is absent."""
    default_workspace = tmp_path / "workspaces" / "default"
    default_workspace.mkdir(parents=True, exist_ok=True)

    _patch_test_working_dir(monkeypatch, tmp_path)
    _write_root_config(default_workspace, language="en")

    migration_module._do_ensure_default_agent()

    expected_files = {
        path.name for path in _template_dir("en").glob("*.md")
    }
    assert expected_files <= {
        path.name for path in default_workspace.glob("*.md")
    }
    assert (
        default_workspace / "AGENTS.md"
    ).read_text(encoding="utf-8") == (
        _template_dir("en") / "AGENTS.md"
    ).read_text(encoding="utf-8")


def test_visible_workspace_files_filter_to_template_and_enabled_prompts(
    monkeypatch,
    tmp_path,
):
    """Workspace file UI should hide unrelated migrated markdown files."""
    from copaw.agents.utils import get_visible_workspace_md_filenames

    default_workspace = tmp_path / "workspaces" / "default"
    default_workspace.mkdir(parents=True, exist_ok=True)

    _patch_test_working_dir(monkeypatch, tmp_path)
    _write_root_config(default_workspace, language="zh")
    save_agent_config(
        "default",
        AgentProfileConfig(
            id="default",
            name="Default Agent",
            workspace_dir=str(default_workspace),
            language="zh",
            system_prompt_files=["AGENTS.md", "SOUL.md", "PROFILE.md"],
        ),
    )

    migration_module._do_ensure_default_agent()
    (default_workspace / "README.md").write_text("# Readme\n", encoding="utf-8")
    (default_workspace / "CUSTOM_PROMPT.md").write_text(
        "# Custom prompt\n",
        encoding="utf-8",
    )

    agent_config = load_agent_config("default")
    visible_filenames = get_visible_workspace_md_filenames(
        agent_config.language,
        extra_filenames=[*agent_config.system_prompt_files, "CUSTOM_PROMPT.md"],
    )

    listed_files = {
        item["filename"]
        for item in AgentMdManager(default_workspace).list_working_mds(
            visible_filenames,
        )
    }

    assert "README.md" not in listed_files
    assert "CUSTOM_PROMPT.md" in listed_files
    assert {
        "AGENTS.md",
        "BOOTSTRAP.md",
        "HEARTBEAT.md",
        "MEMORY.md",
        "PROFILE.md",
        "SOUL.md",
    } <= listed_files
