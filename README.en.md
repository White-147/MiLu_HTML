<p align="center">
  <img src="./console/public/milu-logo.png" alt="MiLuAssistantWeb logo" width="170">
</p>

<h1 align="center">MiLuAssistantWeb</h1>

<p align="center">A MiLu web assistant edition derived from the CoPaw / QwenPaw project line, with model configuration, skills, workspaces, memory, and a web console.</p>

<p align="center">
  <a href="./README.md">简体中文</a> | <a href="./README.en.md">English</a>
</p>

<p align="center">
  <a href="https://github.com/White-147/MiLuAssistantWeb/actions/workflows/tests.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/White-147/MiLuAssistantWeb/tests.yml?branch=main&style=for-the-badge&label=tests"></a>
  <img alt="Stack" src="https://img.shields.io/badge/stack-Python%20%2B%20FastAPI%20%2B%20React-2E7D32?style=for-the-badge">
  <img alt="Mode" src="https://img.shields.io/badge/mode-local%20or%20self--hosted-F59E0B?style=for-the-badge">
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue?style=for-the-badge"></a>
</p>

<p align="center">
  <img src="./docs/assets/screenshots/console-overview.png" alt="MiLuAssistantWeb console screenshot" width="900">
</p>

MiLuAssistantWeb is a web-based personal AI assistant adapted from the CoPaw / QwenPaw project line. It keeps the original multi-channel assistant, skills, model provider, workspace, memory, and security concepts while rebranding and adapting the application into the MiLu web edition.

## Positioning

- **Upstream basis**: CoPaw / QwenPaw by AgentScope.
- **Project role**: Web edition of the MiLu assistant project.
- **Follow-up package**: [MiLuAssistantDesktop](https://github.com/White-147/MiLuAssistantDesktop), the Windows desktop installer version based on this web edition.
- **Main scenario**: Local or self-hosted AI assistant with configurable models, skills, channels, files, memory, and scheduled tasks.

## Main Changes

- Renamed the Python package, CLI entry, runtime namespace, working directory, and environment variables from the original assistant project to `milu`.
- Replaced web console branding assets with MiLu-related icons and product naming.
- Added MiLu-specific local provider configuration and workspace defaults.
- Cleaned runtime data, user workspaces, and private custom configuration before publishing.
- Prepared this web edition as the base project for the Windows desktop installer.

## Tech Stack

- **Backend**: Python, FastAPI / Uvicorn, AgentScope, AgentScope Runtime.
- **Frontend**: React, TypeScript, Vite, Ant Design.
- **AI capabilities**: model provider configuration, skills, memory, multi-agent collaboration, MCP tools, browser/file/Office/PDF-related skills.
- **Deployment**: local Python runtime, web console, optional Docker-based deployment inherited from the upstream project.

## Local Development

```powershell
cd D:\code\MiLuAssistantWeb
pip install -e .
milu init --defaults
milu app
```

Then open:

```text
http://127.0.0.1:8088/
```

The console can also be launched separately for UI inspection:

```powershell
cd D:\code\MiLuAssistantWeb\console
npm install
npm run dev
```

## Relationship With MiLuAssistantDesktop

This repository provides the web application and Python backend. The desktop installer repository packages this project into an Electron / NSIS Windows application, starts the Python backend locally, loads the web UI in a native window, and isolates user data under the Windows local app data directory.

## License and Security

This project keeps the Apache License 2.0 inherited from the upstream CoPaw / QwenPaw project line. See [LICENSE](LICENSE).

Security reporting instructions are in [SECURITY.md](SECURITY.md), and contribution notes are in [CONTRIBUTING.md](CONTRIBUTING.md).
