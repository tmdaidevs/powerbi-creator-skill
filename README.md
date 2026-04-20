# Power BI Creator Skill

A [GitHub Copilot CLI](https://githubnext.com/projects/copilot-cli/) skill for creating, designing, and managing Power BI reports programmatically. Combines the **Power BI Design MCP Server** with a Copilot CLI skill definition so that an AI assistant can build and style PBIR-format reports end-to-end.

## Features

- **34 MCP tools** spanning discovery, styling, visual CRUD, page management, validation, persistence, and governance
- **Customisable style guide** — ships with a blank `style_guide.example.json` template; create your own brand-specific guide
- **Auto theme injection** — `dataColors` from the style guide are automatically injected as a Power BI custom theme so charts pick up the palette globally
- **Conditional formatting** via `FillRule` + `linearGradient2` with `dataViewWildcard` selectors
- **Overlap & gap validation** — layout rules enforce 20 px gaps/margins; overlapping visuals are blocked before they reach Fabric
- **Automatic backups** — every write operation snapshots the prior definition; full rollback support
- **Audit logging** — every mutation is recorded with timestamp, tool, workspace, and report IDs
- **Bulk governance** — apply a style guide across multiple reports in one call
- **Dry-run mode** — preview every change before committing

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/tmdaidevs/powerbi-creator-skill.git
cd powerbi-creator-skill
```

### 2. Create a Python virtual environment

```bash
cd mcp-server
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

### 4. Configure authentication

Copy the example env file and fill in your credentials:

```bash
cp examples/.env.example .env
```

Edit `.env` with your Azure / Fabric credentials (see [Authentication](#authentication) below).

### 5. Register the skill in Copilot CLI

Copy or symlink the skill and MCP config into your Copilot CLI skills directory, or point Copilot CLI at this repo's `skill/` folder.

```
skill/powerbi-creator.skill.md   → skill definition
skill/mcp.json                   → MCP server configuration
```

## Authentication

The MCP server authenticates against the Fabric REST API. Three modes are supported:

| Mode | Env vars | When to use |
|---|---|---|
| **Service Principal** | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | CI / automation |
| **Managed Identity** | (none — uses `DefaultAzureCredential`) | Azure-hosted agents |
| **Delegated / Device-code** | `AZURE_TENANT_ID` | Local development |

All modes require the `https://analysis.windows.net/powerbi/api/.default` scope.

## Style Guide

The repo includes a blank style guide template at [`mcp-server/examples/style_guide.example.json`](mcp-server/examples/style_guide.example.json). Copy it and customise it with your brand colors. It defines:

- **dataColors** — ordered palette injected as a Power BI custom theme
- **backgrounds** — page and visual background fills with transparency
- **categoryColors** — deterministic color mapping for known dimension values (e.g., status fields)
- **layoutRules** — gap sizes, margins, and overlap-prevention settings

See [`docs/style-guide.md`](docs/style-guide.md) for the full format reference.

## Architecture

The MCP server is organised into six layers:

1. **Auth** (`src/auth/`) — token acquisition via `azure-identity`
2. **Fabric Client** (`src/fabric_client/`) — REST calls to the Fabric / Power BI API
3. **Parser** (`src/parser/`) — PBIR definition decoding, page/visual extraction
4. **Transformations** (`src/transformations/`) — style application, theme injection, conditional formatting, layout engine
5. **Validation** (`src/validation/`) — overlap detection, gap enforcement, definition integrity checks
6. **MCP Tools** (`src/mcp_tools/`) — thin tool wrappers exposed over the MCP protocol

## Project Layout

```
powerbi-creator-skill/
├── README.md
├── LICENSE
├── .gitignore
├── mcp-server/            ← Power BI Design MCP Server
│   ├── src/
│   ├── tests/
│   ├── examples/
│   ├── pyproject.toml
│   └── README.md
├── skill/
│   ├── powerbi-creator.skill.md   ← Copilot CLI skill definition
│   └── mcp.json                    ← MCP server config template
└── docs/
    ├── setup.md
    └── style-guide.md
```

## License

[MIT](LICENSE) © 2026 tmdaidevs
