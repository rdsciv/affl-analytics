#!/usr/bin/env python3
"""
AFFL Viewer Bridge
Serves site/ on http://127.0.0.1:8788
WebSocket control on ws://127.0.0.1:9876
"""
import asyncio
import json
import logging
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, HTTPServer
from threading import Thread
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Configuration
HTTP_PORT = 8788
WS_PORT = 9876
SITE_DIR = Path(__file__).parent.parent / 'site'

# WebSocket clients and last state
ws_clients = set()
last_state = {'year': 2025, 'chart': 'standings', 'team': None}


# ============ HTTP Server ============
class AFFlHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)
    
    def log_message(self, format, *args):
        log.info(f"{self.address_string()} - {format % args}")

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.send_header('Expires', '0')
        super().end_headers()


def run_http_server():
    server = HTTPServer(('127.0.0.1', HTTP_PORT), AFFlHandler)
    log.info(f"HTTP server started on http://127.0.0.1:{HTTP_PORT}")
    log.info(f"Open http://127.0.0.1:{HTTP_PORT}/live.html in your browser")
    server.serve_forever()


# ============ WebSocket Server ============
async def ws_handler(websocket):
    ws_clients.add(websocket)
    log.info(f"WS client connected (total: {len(ws_clients)})")
    
    # Send current state to new client
    try:
        await websocket.send(json.dumps({'type': 'state', **last_state}))
    except Exception as e:
        log.error(f"Error sending initial state: {e}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                log.info(f"Received from client: {data}")
                # Broadcast non-state commands to all clients
                if isinstance(data, dict) and data.get('type') != 'state':
                    await broadcast(data)
            except json.JSONDecodeError:
                log.warning(f"Invalid JSON from client: {message}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)
        log.info(f"WS client disconnected (remaining: {len(ws_clients)})")


async def broadcast(message):
    """Broadcast message to all connected clients"""
    if not ws_clients:
        log.debug("No clients to broadcast to")
        return
    
    data = json.dumps(message)
    log.info(f"Broadcasting to {len(ws_clients)} client(s): {data}")
    
    # Update last state
    if message.get('type') == 'set_season' and 'year' in message:
        last_state['year'] = message['year']
    if message.get('type') == 'set_chart' and 'chart' in message:
        last_state['chart'] = message['chart']
    if message.get('type') == 'highlight_team':
        last_state['team'] = message.get('team')
    
    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send(data)
        except Exception as e:
            log.error(f"Error sending to client: {e}")
            disconnected.add(ws)
    
    for ws in disconnected:
        ws_clients.discard(ws)


async def run_ws_server():
    server = await websockets.serve(ws_handler, '127.0.0.1', WS_PORT)
    log.info(f"WebSocket server started on ws://127.0.0.1:{WS_PORT}")
    await server.wait_closed()


# ============ Public API for MCP Server ============
async def send_command(command_type, **params):
    """Send a command to all connected viewers"""
    message = {'type': command_type, **params}
    await broadcast(message)


def get_state():
    """Get current viewer state"""
    return dict(last_state)


# ============ Main ============
def main():
    # Start HTTP server in background thread
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Run WebSocket server
    try:
        asyncio.run(run_ws_server())
    except KeyboardInterrupt:
        log.info("Shutting down...")


if __name__ == '__main__':
    main()
