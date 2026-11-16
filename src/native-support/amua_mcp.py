#!/usr/bin/env python3
"""AMUA MCP server over stdio, with a private file bridge to the running app.

No pip packages, shell evaluation, network ports or API credentials are used.
Run with --call OPERATION '{JSON}' for direct operation from a Codex shell
before a newly configured MCP connection has been loaded into its tool list.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import base64
try:
    import fcntl
except ImportError:
    import windows_locking as fcntl
import json
import math
import re
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

WINDOWS=sys.platform=='win32'
APP=(Path(__file__).resolve().parent.parent/'Amua.exe') if WINDOWS else (Path(__file__).resolve().parents[2] if Path(__file__).resolve().parent.name=='Resources' else Path(__file__).resolve().parents[2]/'Amua.app')
SUPPORT=(Path(os.environ.get('AMUA_TEST_SUPPORT',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Amua-v3.3.2'))) if WINDOWS else Path.home()/'Library/Application Support/Amua-v3.3.2')
BRIDGE = SUPPORT / 'bridge'
VERSION = '3.3.2'
os.umask(0o077)

CLIENT_NAME='Local MCP client'
def access_enabled():
    path=SUPPORT/'mcp-access.properties'
    if not path.exists():return True
    try:
        if path.is_symlink() or path.stat().st_size>4096:return False
        values={}
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith(('#','!')):
                key,value=line.split('=',1);values[key.strip()]=value.strip()
        return values.get('enabled')=='true'
    except OSError:return False

def record_client(method):
    if CLIENT_NAME=='Amua connection test':return
    # Connection metadata only: never tool arguments, prompts, model paths or credentials.
    try:
        SUPPORT.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=SUPPORT/'mcp-last-client.json';temp=SUPPORT/('mcp-last-client-'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps({'client':CLIENT_NAME,'method':method,'at_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())}))
        temp.replace(path)
    except OSError:pass

def self_test():
    initialized=handle({'method':'initialize','params':{'protocolVersion':'2025-11-25','clientInfo':{'name':'Amua connection test'}}})
    tools=handle({'method':'tools/list'})['tools']
    enabled=access_enabled()
    if not enabled:return {'ok':False,'access_enabled':False,'server_version':VERSION,'tools_available':len(tools),'message':'Enable local MCP access in Amua first.'}
    observed=execute('status',{})
    ready=bool(observed.get('ready') and observed.get('responsive'))
    return {'ok':ready,'access_enabled':True,'server_version':initialized['serverInfo']['version'],'tools_available':len(tools),'app_ready':ready,'message':'Local MCP connection is ready.' if ready else 'The server is ready; open Amua 3.3.2 to finish connecting.'}

def state():
    stopped = {'running':False, 'ready':False, 'responsive':False, 'state':'stopped'}
    try:
        raw = (SUPPORT / 'status.json').read_bytes()
        if len(raw) > 1024*1024: return dict(stopped, state='invalid-status')
        result = json.loads(raw)
        if not isinstance(result,dict): return dict(stopped,state='invalid-status')
        if any(type(result.get(k)) is not bool for k in ('running','ready')): return dict(stopped,state='invalid-status')
        pid=result.get('pid'); heartbeat=result.get('heartbeat_ms')
        if type(pid) is not int or pid <= 0 or type(heartbeat) not in (int,float) or not math.isfinite(heartbeat):
            return dict(stopped,state='invalid-status')
        if not isinstance(result.get('instance'),str) or not result['instance']: return dict(stopped,state='invalid-status')
        alive=False
        if WINDOWS:
            from windows_process import pid_alive
            alive=pid_alive(pid)
        else:
            try:os.kill(pid,0);alive=True
            except PermissionError:alive=True
            except OSError:pass
        age=time.time()*1000-heartbeat
        fresh= -1000 <= age < 5000
        result.update(running=result['running'] and alive,ready=result['ready'] and alive,
                      responsive=result['ready'] and alive and fresh)
        result['state']='stopped' if not alive else ('responsive' if result['responsive'] else 'unresponsive')
        return result
    except (OSError,ValueError,TypeError): return dict(stopped,state='invalid-status')

def request(method, params=None, timeout=15):
    BRIDGE.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Serialize independent MCP clients as well as command-line calls.
    with (SUPPORT / 'client.lock').open('a') as lock:
        lock_deadline=time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=lock_deadline:
                    raise RuntimeError('Another AMUA client is busy; try again shortly.')
                time.sleep(.04)
        current = state()
        if method=='status' and not current.get('responsive') and not (params or {}).get('operation_id'):
            return current
        if not current.get('ready'):
            if method == 'status':
                return current
            raise RuntimeError('Amua is not ready. Use amua_launch first.')
        if not current.get('responsive'):
            # A background Java window may have its timers throttled by macOS.
            # Send a normal reopen event to wake its window; do not disable
            # system power management or mistake this for process termination.
            if WINDOWS:subprocess.Popen([str(APP)],creationflags=subprocess.CREATE_NO_WINDOW)
            else:subprocess.run(['/usr/bin/open','-g',str(APP)],capture_output=True,timeout=5)
        ident = uuid.uuid4().hex
        sent = BRIDGE / (ident + '.request.json')
        received = BRIDGE / (ident + '.response.json')
        temporary = sent.with_suffix('.tmp')
        payload = {'id': ident, 'instance': current['instance'], 'method': method,
                   'params': params or {}, 'deadline': time.time()+timeout,
                   'token':(SUPPORT/'bridge.token').read_text()}
        temporary.write_text(json.dumps(payload))
        temporary.replace(sent)
        deadline = time.monotonic()+timeout
        last_process_check=0
        try:
            while time.monotonic() < deadline:
                if received.exists():
                    reply = json.loads(received.read_text())
                    if 'error' in reply:
                        raise RuntimeError(reply['error'])
                    return reply['result']
                if time.monotonic()-last_process_check>.2:
                    last_process_check=time.monotonic()
                    observed=state()
                    if not observed.get('running'):
                        if method=='status':return observed
                        raise RuntimeError('Amua exited before replying to '+method)
                time.sleep(0.04)
            raise RuntimeError('Amua did not respond in time. Check its window for a busy analysis or dialog.')
        finally:
            sent.unlink(missing_ok=True)
            received.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)

def launch(params=None):
    params = params or {}
    if not (APP.is_file() if WINDOWS else APP.is_dir()):raise RuntimeError('Amua is not installed at '+str(APP))
    if state().get('ready') and state().get('responsive'):return request('activate')
    if WINDOWS:subprocess.Popen([str(APP)],creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        opened=subprocess.run(['/usr/bin/open',str(APP)],capture_output=True,text=True)
        if opened.returncode:raise RuntimeError('macOS could not launch Amua: '+opened.stderr.strip())
    deadline = time.monotonic()+25
    while time.monotonic() < deadline:
        if state().get('ready'):
            return request('status')
        time.sleep(0.15)
    raise RuntimeError('Amua has not become ready. See '+str(SUPPORT / 'Amua.log'))

def prop(kind, description=None, **extra):
    result = {'type': kind, **extra}
    if description:
        result['description'] = description
    return result

def tool(operation, description, properties=None, required=None, read=False):
    return {'name': 'amua_'+operation, 'description': description,
        'inputSchema': {'type':'object', 'properties': properties or {},
                        'required': required or [], 'additionalProperties':False},
        'annotations': {'readOnlyHint':read, 'destructiveHint':not read,
                        'idempotentHint':read, 'openWorldHint':False}}

ID = prop('string', 'Component id returned by amua_inspect, e.g. c42.')
TOOLS = [
    tool('launch', 'Launch or focus the installed Amua app. Does not open or alter a model.'),
    tool('status', 'Read process state, UI responsiveness and operations. A completed Run click starts AMUA’s own worker; inspect console for analysis completion.', {'operation_id':prop('string')},read=True),
    tool('inspect', 'Read visible AMUA windows and Swing controls, including menus, labels, editable fields, tables and stable component ids. Inspect before acting; inspect again after a dialog opens.',
         {'max_nodes':prop('integer',minimum=1,maximum=3000), 'window':prop('string')}, read=True),
    tool('click', 'Click an enabled AMUA button or actionable menu item by component id. Returns an operation id; inspect/status shows the outcome and any resulting modal dialog.', {'id':ID}, ['id']),
    tool('menu', 'Invoke an exact AMUA menu path, using labels obtained from inspection, e.g. ["Model", "New", "Decision Tree"]. Returns before modal dialogs close.',
         {'path':prop('array',items={'type':'string'},minItems=1)}, ['path']),
    tool('set_text', 'Set an editable text field in AMUA. Set commit=true for an on-canvas node expression/name that commits on focus loss. For dialogs, fill fields then click their Save/OK button.',
         {'id':ID, 'text':prop('string'), 'commit':prop('boolean')}, ['id','text']),
    tool('select', 'Select a tab, combo-box or list index, a table row/column, or a numeric spinner/slider value.',
         {'id':ID,'index':prop('integer',minimum=0),'row':prop('integer',minimum=0),
          'column':prop('integer',minimum=0),'value':prop('number')}, ['id']),
    tool('table', 'Read a bounded page of an AMUA table including column names.',
         {'id':ID,'offset':prop('integer',minimum=0),'limit':prop('integer',minimum=1,maximum=500)}, ['id'],read=True),
    tool('set_cell', 'Set a cell only if AMUA marks it editable. Use the app’s Edit dialog for read-only model tables.',
         {'id':ID,'row':prop('integer',minimum=0),'column':prop('integer',minimum=0),'value':{'type':['string','number','boolean','null']}},['id','row','column','value']),
    tool('new_model', 'Create an empty decision tree or Markov model in a new AMUA tab.',
         {'type':prop('string',enum=['decision_tree','markov'])},['type']),
    tool('open_model', 'Open a local .amua file in the app or switch to its tab if already open.',
         {'path':prop('string','Absolute path to the .amua file.')},['path']),
    tool('save_model', 'Save the active model to an .amua file. New files require a path; replacing any existing file requires overwrite=true. Review the intended destination before saving.',
         {'path':prop('string'),'overwrite':prop('boolean')}),
    tool('model_summary', 'Read the active model’s parameters, variables, node indices/coordinates, dimensions and simulation settings.',read=True),
    tool('validate_model', 'Perform AMUA’s original full Check Model workflow, including analysis settings, model objects and probabilities. Returns validity, console diagnostics and validation scope.'),
    tool('run_model', 'Use AMUA’s Run Model action on the active model. The app runs analysis in its existing worker thread. Read console/status and inspect resulting windows for completion.'),
    tool('console', 'Read recent AMUA console output, including analysis results and errors.',
         {'limit':prop('integer',minimum=1,maximum=100000)},read=True),
    tool('canvas_click', 'Send a mouse click to a visible AMUA canvas/component using coordinates relative to that component. Use model_summary for node coordinates and inspect for canvas ids.',
         {'id':ID,'x':prop('integer',minimum=0),'y':prop('integer',minimum=0),
          'click_count':prop('integer',minimum=1,maximum=2),'button':prop('integer',enum=[1,3])},['id','x','y']),
    tool('screenshot', 'Render a visible AMUA window as a PNG image without capturing other apps or requiring macOS screen-recording permission.',
         {'window':prop('string','Window component id; defaults to main window.')},read=True),
]
TOOL_MAP = {t['name']:t for t in TOOLS}

def execute(operation, arguments):
    if operation!='launch' and not access_enabled():
        if operation=='status':return {'access_enabled':False,'message':'MCP access is disabled. Enable MCP Access beside Help in Amua 3.3.2.'}
        raise RuntimeError('MCP access is disabled. Enable MCP Access beside Help in Amua 3.3.2.')
    if 'amua_'+operation in TOOL_MAP:record_client('amua_'+operation)
    if operation == 'launch':
        return launch(arguments)
    if 'amua_'+operation not in TOOL_MAP:
        raise ValueError('Unknown AMUA tool: '+operation)
    schema = TOOL_MAP['amua_'+operation]['inputSchema']
    for key in schema['required']:
        if key not in arguments:
            raise ValueError('Missing required argument: '+key)
    unexpected = set(arguments) - set(schema['properties'])
    if unexpected:
        raise ValueError('Unexpected arguments: '+', '.join(sorted(unexpected)))
    for key, value in arguments.items():
        spec = schema['properties'][key]
        expected = spec['type'] if isinstance(spec['type'],list) else [spec['type']]
        valid = (('string' in expected and isinstance(value,str)) or
                 ('integer' in expected and type(value) is int) or
                 ('number' in expected and type(value) in (int,float) and math.isfinite(value)) or
                 ('boolean' in expected and type(value) is bool) or
                 ('null' in expected and value is None) or
                 ('array' in expected and isinstance(value,list) and all(isinstance(v,str) for v in value)))
        if not valid:
            raise ValueError('Invalid argument type: '+key)
        if 'enum' in spec and value not in spec['enum']:
            raise ValueError('Invalid argument value: '+key)
        if 'minimum' in spec and value < spec['minimum']:
            raise ValueError('Argument below minimum: '+key)
        if 'maximum' in spec and value > spec['maximum']:
            raise ValueError('Argument above maximum: '+key)
    if operation == 'select':
        if not any(k in arguments for k in ('index','row','value')):
            raise ValueError('Select requires index, row or value.')
    result=request(operation, arguments)
    if operation=='validate_model':
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            status=request('status',{'operation_id':result['operation_id']},timeout=60)
            action=status.get('operation')
            if action and action['state']=='completed':
                return action['result']
            if action and action['state']=='error':
                raise RuntimeError(action['error'])
            time.sleep(.05)
        raise RuntimeError('Validation is still pending; check operation '+result['operation_id'])
    return result

def handle(message):
    global CLIENT_NAME
    method = message.get('method')
    params = message.get('params') or {}
    if method == 'initialize':
        info=params.get('clientInfo') or {}
        name=info.get('name') if isinstance(info,dict) else None
        if isinstance(name,str):CLIENT_NAME=re.sub(r'[^A-Za-z0-9 ._()-]','',name)[:80] or 'MCP client'
        record_client('initialize')
        requested = params.get('protocolVersion')
        protocol = requested if requested in ('2024-11-05','2025-03-26','2025-06-18','2025-11-25') else '2025-11-25'
        return {'protocolVersion': protocol,
                'capabilities': {'tools': {'listChanged':False}},
                'serverInfo': {'name':'amua-desktop', 'version':VERSION},
                'instructions':'Operate the local Amua app only for the user’s requested work. Launch, inspect, then act using observed controls. Inspect modal dialogs after actions. Save to a new path unless overwriting was intended. No arbitrary code execution tool is exposed.'}
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools':TOOLS}
    if method == 'tools/call':
        name = params.get('name','')
        if name not in TOOL_MAP:
            return {'isError':True,'content':[{'type':'text','text':'Unknown tool: '+name}]}
        try:
            operation = name.removeprefix('amua_')
            data = execute(operation, params.get('arguments') or {})
            if operation == 'screenshot':
                path = Path(data['path']).resolve()
                if path.parent != SUPPORT.resolve() or not path.name.startswith('snapshot-'):
                    raise RuntimeError('Unexpected screenshot path.')
                try:
                    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
                finally:
                    path.unlink(missing_ok=True)
                return {'content':[{'type':'image','mimeType':'image/png','data':encoded},
                                   {'type':'text','text':json.dumps({'width':data['width'],'height':data['height']})}]}
            return {'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False)}],
                    'structuredContent':data}
        except Exception as exc:
            return {'isError':True, 'content':[{'type':'text','text':str(exc)}]}
    raise ValueError('Method not found: '+str(method))

class RpcError(Exception):
    def __init__(self,code,message): self.code=code; super().__init__(message)

def rpc(message):
    if not isinstance(message,dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'),str):
        raise RpcError(-32600,'Invalid request')
    if 'id' in message and (isinstance(message['id'],(dict,list,bool))): raise RpcError(-32600,'Invalid request ID')
    if 'params' in message and not isinstance(message['params'],dict): raise RpcError(-32602,'Invalid params')
    if message['method'] not in ('initialize','ping','tools/list','tools/call') and not message['method'].startswith('notifications/'):
        raise RpcError(-32601,'Method not found')
    if message['method'].startswith('notifications/'): return None
    params=message.get('params',{})
    if message['method']=='tools/call' and (not isinstance(params.get('name'),str) or not isinstance(params.get('arguments',{}),dict)):
        raise RpcError(-32602,'Invalid tool params')
    return handle(message)

def serve():
    for line in sys.stdin:
        message=None
        try:
            try: message=json.loads(line)
            except ValueError: raise RpcError(-32700,'Parse error')
            result=rpc(message)
            if 'id' not in message: continue
            reply={'jsonrpc':'2.0','id':message['id'],'result':result}
        except RpcError as exc:
            if isinstance(message,dict) and 'id' not in message and exc.code != -32600: continue
            reply={'jsonrpc':'2.0','id':message.get('id') if isinstance(message,dict) else None,'error':{'code':exc.code,'message':str(exc)}}
        except Exception:
            if isinstance(message,dict) and 'id' not in message: continue
            reply={'jsonrpc':'2.0','id':message.get('id') if isinstance(message,dict) else None,'error':{'code':-32603,'message':'Internal error'}}
        print(json.dumps(reply,ensure_ascii=False),flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true',help='Check local MCP discovery and app readiness without modifying a model.')
    parser.add_argument('--call', metavar='OPERATION')
    parser.add_argument('--check', action='store_true', help='Launch and perform read-only live activation checks.')
    parser.add_argument('arguments', nargs='?', default='{}')
    args = parser.parse_args()
    if args.check:
        launch()
        current = request('status')
        view = request('inspect',{'max_nodes':1000})
        console = request('console',{'limit':1000})
        if not current.get('ready') or not view.get('windows'):
            raise RuntimeError('The AMUA control bridge is not ready or has no visible window.')
        result = {'checked_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  'live_app_ready':True,'visible_windows':len(view['windows']),
                  'controls_inspected':view['nodes'],'console_read':isinstance(console.get('text'),str),
                  'java':current['java'],'architecture':current['architecture'],
                  'note':'Read-only live checks passed. No model was created, changed or run.'}
        (SUPPORT/'activation-check.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    elif args.self_test:
        print(json.dumps(self_test(),indent=2))
    elif args.call:
        print(json.dumps(execute(args.call,json.loads(args.arguments)),indent=2,ensure_ascii=False))
    else:
        serve()

if __name__ == '__main__':
    main()
