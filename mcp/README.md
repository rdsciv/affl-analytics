# AFFL MCP — Live Dashboard Control

A Blender-MCP-style system for controlling the AFFL analytics dashboard from your AI assistant.

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Cursor    │◄─stdio─►│ mcp/server.py│◄─calls─►│mcp/bridge.py│
│  (or Grok)  │         │  (MCP tools) │         │   (WS host) │
└─────────────┘         └──────────────┘         └──────┬──────┘
                                                         │ ws://9876
                                                         ▼
                                                  ┌──────────────┐
                                                  │  Browser     │
                                                  │ live.html    │
                                                  └──────────────┘
```

## Setup (3 steps)

### 1. Install dependencies

```bash
pip install -r mcp/requirements.txt
```

### 2. Start the bridge

In one terminal:

```bash
python3 mcp/bridge.py
```

This:
- Serves the `site/` folder on **http://127.0.0.1:8788**
- Opens a WebSocket control socket on **ws://127.0.0.1:9876**
- Broadcasts JSON commands to all connected browser tabs

### 3. Open the live dashboard

Open **http://127.0.0.1:8788/live.html** in your browser.

The page automatically connects to the bridge. If the bridge is not running, you'll see a yellow banner.

## Usage in Cursor

Add this to your Cursor MCP config (usually `~/.cursor/mcp.json` or via Settings → MCP):

```json
{
  "mcpServers": {
    "affl": {
      "command": "python3",
      "args": ["mcp/server.py"],
      "cwd": "/path/to/affl-analytics"
    }
  }
}
```

Replace `/path/to/affl-analytics` with the absolute path to this repo.

Restart Cursor. The MCP tools will appear in the composer.

## Available Tools

- **affl_state** — what year/chart/team is showing
- **affl_set_season** — change year (2014–2025)
- **affl_set_chart** — change chart (`standings`, `luck`, `weekly`, `lineup`, `draft`, `payroll`)
- **affl_highlight_team** — highlight a team by name or abbrev
- **affl_standings** — return the actual standings table for a year (from JSON)
- **affl_open** — instructions for opening the viewer

## Example Queries

- "Show me 2018 luck in AFFL"
- "Switch to weekly scoring and highlight the Gringos"
- "What are the 2025 standings?"

The live dashboard updates in real time as the MCP server sends commands.

## Notes

- No D1, no Supabase, no hosted services
- All data loaded from committed JSON files in `site/`
- If a chart has no data for a season (e.g. Lineup IQ pre-2018), the viewer shows an honest message
- Multiple browser tabs can connect to the same bridge; they all update together
