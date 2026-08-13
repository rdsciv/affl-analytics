#!/usr/bin/env python3
"""
AFFL MCP Server
Stdio MCP server for controlling the AFFL live dashboard
"""
import asyncio
import json
import sys
from pathlib import Path
import websockets

# Import MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Configuration
WS_URL = 'ws://127.0.0.1:9876'

# Data paths
WORKSPACE = Path(__file__).parent.parent
DATA_FILE = WORKSPACE / 'site' / 'data.json'
YEARS_DIR = WORKSPACE / 'site' / 'years'

# State
league_data = None
available_years = []
bridge_state = {'year': 2025, 'chart': 'standings', 'team': None}


def load_data():
    global league_data, available_years
    try:
        with open(DATA_FILE) as f:
            league_data = json.load(f)
        available_years = sorted([int(f.stem) for f in YEARS_DIR.glob('*.json')], reverse=True)
    except Exception as e:
        print(f"Warning: Could not load data: {e}", file=sys.stderr)
        league_data = {'seasons': {}, 'members': {}}
        available_years = []


async def send_command(command_type, **params):
    """Send a command to the bridge via WebSocket"""
    message = {'type': command_type, **params}
    try:
        async with websockets.connect(WS_URL, close_timeout=1) as ws:
            await ws.send(json.dumps(message))
            # Update local state
            if command_type == 'set_season' and 'year' in params:
                bridge_state['year'] = params['year']
            elif command_type == 'set_chart' and 'chart' in params:
                bridge_state['chart'] = params['chart']
            elif command_type == 'highlight_team':
                bridge_state['team'] = params.get('team')
    except Exception as e:
        print(f"Warning: Could not connect to bridge: {e}", file=sys.stderr)


def get_state():
    """Get current state"""
    return dict(bridge_state)


load_data()


# ============ MCP Handlers ============
async def handle_list_tools(context, params):
    """List available tools"""
    return types.ListToolsResult(tools=[
        types.Tool(
            name="affl_state",
            description="Get the current state of the AFFL live dashboard (year, chart type, highlighted team)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="affl_set_season",
            description="Change the season/year displayed in the live dashboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": f"Season year (available: {', '.join(map(str, available_years))})",
                        "minimum": 2014,
                        "maximum": 2025
                    }
                },
                "required": ["year"]
            }
        ),
        types.Tool(
            name="affl_set_chart",
            description="Change the chart type displayed in the live dashboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "chart": {
                        "type": "string",
                        "description": "Chart type to display",
                        "enum": ["standings", "luck", "weekly", "lineup", "draft", "payroll"]
                    }
                },
                "required": ["chart"]
            }
        ),
        types.Tool(
            name="affl_highlight_team",
            description="Highlight a specific team in the current chart, or clear highlight if team is empty",
            inputSchema={
                "type": "object",
                "properties": {
                    "team": {
                        "type": "string",
                        "description": "Team abbreviation or name (e.g., 'TIJ', 'Tijuana Sanchitos'), or empty to clear"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="affl_standings",
            description="Get the standings table for a specific season from the league data",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": f"Season year (available: {', '.join(map(str, available_years))})",
                        "minimum": 2014,
                        "maximum": 2025
                    }
                },
                "required": ["year"]
            }
        ),
        types.Tool(
            name="affl_open",
            description="Get instructions for opening the AFFL live dashboard",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ])


async def handle_call_tool(context, params):
    """Handle tool calls"""
    name = params.name
    arguments = params.arguments or {}
    
    if name == "affl_state":
        state = get_state()
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=json.dumps(state, indent=2))
        ])
    
    elif name == "affl_set_season":
        year = arguments["year"]
        if year not in available_years:
            return types.CallToolResult(content=[
                types.TextContent(
                    type="text",
                    text=f"Error: Year {year} not available. Available years: {', '.join(map(str, available_years))}"
                )
            ])
        await send_command('set_season', year=year)
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"Season set to {year}")
        ])
    
    elif name == "affl_set_chart":
        chart = arguments["chart"]
        await send_command('set_chart', chart=chart)
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"Chart set to {chart}")
        ])
    
    elif name == "affl_highlight_team":
        team = arguments.get("team", "")
        await send_command('highlight_team', team=team if team else None)
        if team:
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=f"Highlighting team: {team}")
            ])
        else:
            return types.CallToolResult(content=[
                types.TextContent(type="text", text="Cleared team highlight")
            ])
    
    elif name == "affl_standings":
        year = arguments["year"]
        if year not in available_years:
            return types.CallToolResult(content=[
                types.TextContent(
                    type="text",
                    text=f"Error: Year {year} not available. Available years: {', '.join(map(str, available_years))}"
                )
            ])
        
        year_file = YEARS_DIR / f"{year}.json"
        try:
            with open(year_file) as f:
                year_data = json.load(f)
            
            teams = sorted(year_data.get('teams', []), 
                          key=lambda t: (-t.get('wins', 0), -t.get('pf', 0)))
            
            lines = [f"=== {year} AFFL Standings ===\n"]
            for i, team in enumerate(teams, 1):
                name = team.get('name', 'Unknown')
                abbrev = team.get('abbrev', '???')
                wins = team.get('wins', 0)
                losses = team.get('losses', 0)
                pf = team.get('pf', 0)
                pa = team.get('pa', 0)
                lines.append(f"{i:2d}. {abbrev:4s} {name:30s} {wins:2d}-{losses:2d}  PF:{pf:7.1f}  PA:{pa:7.1f}")
            
            return types.CallToolResult(content=[
                types.TextContent(type="text", text="\n".join(lines))
            ])
        except Exception as e:
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=f"Error loading standings for {year}: {e}")
            ])
    
    elif name == "affl_open":
        return types.CallToolResult(content=[
            types.TextContent(
                type="text",
                text=(
                    "To open the AFFL live dashboard:\n\n"
                    "1. Make sure the bridge is running: python3 mcp/bridge.py\n"
                    "2. Open http://127.0.0.1:8788/live.html in your browser\n"
                    "3. The page will connect to the bridge automatically\n\n"
                    "You can then use the MCP tools to control the dashboard from your AI assistant."
                )
            )
        ])
    
    return types.CallToolResult(content=[
        types.TextContent(type="text", text=f"Unknown tool: {name}")
    ])


# ============ Main ============
async def main():
    """Run the MCP server"""
    server = Server("affl-mcp", on_list_tools=handle_list_tools, on_call_tool=handle_call_tool)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
