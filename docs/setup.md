# Setup Guide

Detailed instructions for setting up the Power BI Creator Skill and its MCP server.

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **pip** (bundled with Python)
- **Git**
- **Azure / Fabric tenant** with at least one workspace containing PBIR-format reports
- **GitHub Copilot CLI** installed and authenticated

## Step-by-step Installation

### 1. Clone the repository

```bash
git clone https://github.com/tmdaidevs/powerbi-creator-skill.git
cd powerbi-creator-skill
```

### 2. Set up the MCP server

```bash
cd mcp-server
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

Install in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

### 3. Configure authentication

Copy the example environment file:

```bash
cp examples/.env.example .env
```

Edit `.env` and provide your credentials. At minimum you need one of the following configurations:

#### Service Principal (recommended for automation)

```env
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-app-registration-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
```

#### Managed Identity (Azure-hosted environments)

No env vars needed — the server uses `DefaultAzureCredential` which auto-discovers managed identity.

#### Delegated / Device Code (local development)

```env
AZURE_TENANT_ID=<your-tenant-id>
```

The server will prompt for interactive login on first use.

### 4. Verify the server starts

```bash
python -m src.server.mcp_server
```

The server should start and listen for MCP connections. Press `Ctrl+C` to stop.

### 5. Run tests

```bash
pytest tests/ -v
```

### 6. Register the skill

Point your Copilot CLI configuration at the skill files:

- `skill/powerbi-creator.skill.md` — the skill definition with triggers and instructions
- `skill/mcp.json` — the MCP server configuration

The `mcp.json` file tells Copilot CLI how to launch the MCP server. The `cwd` field is relative to the repo root, so the server can locate its `examples/` directory.

## Optional Configuration

### Default style guide

Set the `PBIR_MCP_DEFAULT_STYLE_GUIDE_PATH` environment variable (or configure it in `mcp.json`) to point at your preferred style guide JSON:

```env
PBIR_MCP_DEFAULT_STYLE_GUIDE_PATH=examples/style_guide.example.json
```

### Audit log location

By default the audit log is written to `audit.jsonl` in the MCP server's working directory. Override with:

```env
PBIR_MCP_AUDIT_LOG_PATH=./logs/audit.jsonl
```

### Backup directory

Backups are stored under `backups/` by default. Override with:

```env
PBIR_MCP_BACKUP_DIR=./report_backups
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'src'` | Make sure you ran `pip install -e .` from the `mcp-server/` directory |
| Authentication failures | Verify `.env` values; ensure the service principal has *Contributor* on the target workspace |
| `PBIR definition not found` | The target report must be in PBIR format (not legacy PBIX) |
| Tests fail with import errors | Activate the virtual environment before running `pytest` |
