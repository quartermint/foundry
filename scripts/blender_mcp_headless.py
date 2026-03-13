"""Headless Blender code execution server for Foundry."""
import bpy, sys, io, traceback, threading, time

import subprocess
for pkg in ['fastapi', 'uvicorn']:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])

import uvicorn
from fastapi import FastAPI

app = FastAPI(title='Foundry Blender Server')
exec_lock = threading.Lock()

def _setup_context():
    """Ensure a valid context for operators in background mode."""
    if bpy.context.window:
        return
    # In background mode, override context for operator polls
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(window=window, area=area):
                    pass
                return

@app.get('/health')
def health():
    return {'status': 'ok', 'blender_version': bpy.app.version_string}

@app.get('/mcp/list_tools')
def list_tools():
    return {'tools': [{'name': 'execute_blender_code', 'description': 'Execute arbitrary bpy Python code'}]}

@app.post('/mcp/invoke/execute_blender_code')
def execute_code(body: dict):
    code = body.get('code', '')
    if not code:
        return {'error': 'No code provided'}
    stdout_capture = io.StringIO()
    old_stdout = sys.stdout
    # Build exec globals with common imports available
    exec_globals = {
        '__builtins__': __builtins__,
        'bpy': bpy,
    }
    with exec_lock:
        try:
            sys.stdout = stdout_capture
            exec(code, exec_globals)
            sys.stdout = old_stdout
            return {'success': True, 'output': stdout_capture.getvalue()}
        except Exception as e:
            sys.stdout = old_stdout
            return {'error': f'{type(e).__name__}: {e}', 'traceback': traceback.format_exc()}

def run_server():
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
print('[Foundry Blender] Server started on http://0.0.0.0:8000')

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    sys.exit(0)
