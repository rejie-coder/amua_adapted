"""Official Antigravity ACP for Gemini; isolated Google connections, no API fallback."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid
import signal
import atexit
import re
from contextlib import contextmanager
from broker import fcntl
from broker import BrokerError, SUPPORT

MAX_LINE = 2_000_000
_active_clients = set()
_cleanup_installed = False

def _cleanup_clients():
    for client in tuple(_active_clients):
        client.close()

def _install_cleanup():
    global _cleanup_installed
    if sys.platform == 'win32' or _cleanup_installed:
        return
    atexit.register(_cleanup_clients)
    if threading.current_thread() is threading.main_thread():
        def terminate(signum, frame):
            _cleanup_clients()
            raise SystemExit(128 + signum)
        signal.signal(signal.SIGTERM, terminate)
        _cleanup_installed = True

SETTINGS = {
    'auth': {'type': 'oauth-personal'},
    'agentMode': 'plan', 'toolPermission': 'request-review',
    'permissions': {'allow': [], 'deny': [a+'(*)' for a in
        ('read_file','write_file','read_url','execute_url','download_url','command','mcp')]},
    'enableTelemetry': False, 'historySize': 0,
}


def runtime():
    root = Path(__file__).resolve().parent
    executable = root / 'antigravity' / ('agy.exe' if sys.platform == 'win32' else 'agy')
    if not executable.is_file():
        raise BrokerError('gemini_runtime_missing')
    return [str(executable), 'acp', '--app-data-dir', 'amua', '--gemini-dir', '.gemini',
            '--disable-telemetry', '--include-default-customizations=false']


def environment(home, settings):
    # Own home, settings and credential namespace; never inherit API/billing overrides.
    allow = {'PATH','SystemRoot','SYSTEMROOT','SystemDrive','WINDIR','TEMP','TMP','TMPDIR','LANG','LC_ALL'}
    env = {k:v for k,v in os.environ.items() if k in allow}
    env.update({'HOME':str(home), 'USERPROFILE':str(home),
        'XDG_CONFIG_HOME':str(home/'.config'), 'APPDATA':str(home/'AppData/Roaming'),
        'LOCALAPPDATA':str(home/'AppData/Local'),
        'ANTIGRAVITY_CREDENTIAL_SCOPE':'amua-'+hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:32],
        'AGY_CLI_DISABLE_AUTO_UPDATE':'1','NO_COLOR':'1'})
    return env


def provider_error(method, error):
    code=error.get('code'); reason=str(error.get('message',''))
    if 'no longer supported' in reason.lower() or 'UNSUPPORTED_CLIENT' in reason:
        category='gemini_client_retired'
    elif method=='authenticate': category='gemini_sign_in_failed'
    elif code==-32000: category='gemini_auth_required'
    else: category='gemini_request_failed'
    failure=BrokerError(category)
    # Error messages only; no RPC data, OAuth URLs, codes or tokens enter UI/logs.
    reason=re.sub(r'https?://\S+','[provider URL]',reason)
    reason=re.sub(r'(?i)(access_token|refresh_token|id_token|authorization|code|state)[\s:=]+[^\s,;]+',r'\1=[redacted]',reason)
    reason=re.sub(r'eyJ[A-Za-z0-9_.-]{20,}','[redacted]',reason)[:600]
    failure.details={'category':category,'message':('Google sign-in failed. ' if method=='authenticate' else 'Gemini could not complete the request. ')+reason}
    return failure


class ACP:
    def __init__(self, command, home, timeout=180):
        home.mkdir(parents=True, exist_ok=True)
        self.cwd = home / 'empty-workspace'; self.cwd.mkdir(exist_ok=True)
        settings = home / '.gemini/amua/settings.json'
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(SETTINGS), encoding='utf-8')
        self.timeout = timeout; self.seq = 0; self.events = queue.Queue(maxsize=128)
        self.session = None; self.closed = False
        # Windows uses an owned job; macOS uses an owned process group and SIGTERM cleanup.
        if sys.platform == 'win32':
            from windows_process import limit_current_process
            limit_current_process()
        self.p = subprocess.Popen(command, cwd=self.cwd, env=environment(home, settings),
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,
                                  start_new_session=sys.platform != 'win32',
                                  creationflags=0x08000000 if sys.platform == 'win32' else 0)
        _active_clients.add(self)
        _install_cleanup()
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.info = self.call('initialize', {'protocolVersion': 1,
                'clientInfo': {'name': 'amua', 'version': '3.3.3'},
                'clientCapabilities': {'fs': {'readTextFile': False, 'writeTextFile': False}, 'terminal': False}})
            if self.info.get('protocolVersion') != 1: raise BrokerError('gemini_protocol_version')
        except BaseException:
            self.close(); raise

    def _read(self):
        try:
            while not self.closed:
                line = self.p.stdout.readline(MAX_LINE + 1)
                if not line: break
                if len(line) > MAX_LINE: raise ValueError()
                self.events.put(json.loads(line))
        except (ValueError, OSError):
            self.events.put({'_failure': True})
        finally:
            self.events.put(None)

    def send(self, data):
        try:
            self.p.stdin.write((json.dumps(data, ensure_ascii=False)+'\n').encode()); self.p.stdin.flush()
        except (BrokenPipeError, OSError): raise BrokerError('gemini_process_stopped') from None

    def call(self, method, params, emit=None):
        self.seq += 1; ident = self.seq
        self.send({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        last_thought = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise BrokerError('model_chat_stalled')
            try: event = self.events.get(timeout=remaining)
            except queue.Empty: raise BrokerError('model_chat_stalled') from None
            if event is None or event.get('_failure'): raise BrokerError('gemini_protocol_error')
            if 'method' in event and 'id' in event:
                # Never permit shell, file, MCP or other side effects through ACP.
                if event['method'] == 'session/request_permission':
                    self.send({'jsonrpc': '2.0', 'id': event['id'], 'result': {'outcome': {'outcome': 'cancelled'}}})
                else:
                    self.send({'jsonrpc': '2.0', 'id': event['id'], 'error': {'code': -32601, 'message': 'Unavailable in Amua'}})
                continue
            if event.get('method') == 'session/update' and emit:
                params_ = event.get('params', {})
                if params_.get('sessionId') != self.session: raise BrokerError('gemini_session_mismatch')
                update = params_.get('update', {})
                if update.get('sessionUpdate') == 'agent_message_chunk':
                    content = update.get('content', {})
                    if content.get('type') == 'text' and isinstance(content.get('text'), str) and content['text']:
                        emit({'event': 'delta', 'text': content['text']}); deadline = time.monotonic() + self.timeout
                if update.get('sessionUpdate') == 'agent_thought_chunk':
                    content = update.get('content', {})
                    thought = content.get('text')
                    if content.get('type') == 'text' and isinstance(thought, str) and thought:
                        fingerprint = hashlib.sha256(thought.encode()).digest()
                        if fingerprint != last_thought:
                            emit({'event': 'inference_progress', 'phase': 'thinking'})
                            deadline = time.monotonic() + self.timeout
                            last_thought = fingerprint
                # Only phase metadata escapes; thought contents are never logged or shown.
                continue
            if event.get('id') == ident:
                if 'error' in event: raise provider_error(method, event['error'])
                if method in ('authenticate','logout') and event.get('result') is None:return {}
                if not isinstance(event.get('result'), dict): raise BrokerError('gemini_protocol_error')
                return event['result']

    def new_session(self):
        result = self.call('session/new', {'cwd': str(self.cwd.resolve()), 'mcpServers': []})
        self.session = result.get('sessionId')
        if not isinstance(self.session, str) or not self.session: raise BrokerError('gemini_protocol_error')
        return result

    def close(self):
        self.closed = True
        if self.p.poll() is None:
            if sys.platform != 'win32':
                try: os.killpg(self.p.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            else:
                self.p.terminate()
            try: self.p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                if sys.platform != 'win32':
                    try: os.killpg(self.p.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                else:
                    self.p.kill()
                self.p.wait(timeout=1)
        if sys.platform != 'win32':
            # The ACP leader may exit before its backend; its group still belongs to us.
            try: os.killpg(self.p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        for pipe in (self.p.stdin, self.p.stdout):
            try: pipe.close()
            except OSError: pass
        _active_clients.discard(self)


class GeminiBroker:
    def __init__(self):
        self.support = SUPPORT / 'gemini/antigravity'; self.support.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.meta_path = self.support/'connections.json'; self.keychain=self
        self.approved_recipient=None
    def close(self): pass
    @contextmanager
    def operation(self):
        fd=os.open(self.support/'connection.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except (BlockingIOError,OSError): raise BrokerError('gemini_connection_busy') from None
            yield
        finally: os.close(fd)
    def read(self):
        if not self.meta_path.exists():return {'version':1,'active':None,'accounts':{}}
        data=json.loads(self.meta_path.read_text())
        if data.get('version')!=1 or not isinstance(data.get('accounts'),dict):raise BrokerError('gemini_connection_state_invalid')
        for ident in data['accounts']:self.home(ident)
        return data
    def write(self, data):
        temporary=self.support/(uuid.uuid4().hex+'.tmp')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'w') as out:json.dump(data,out);out.flush();os.fsync(out.fileno())
            os.replace(temporary,self.meta_path)
        finally:temporary.unlink(missing_ok=True)
    def home(self, ident):
        if not isinstance(ident,str) or not re.fullmatch(r'google_[a-f0-9]{32}',ident):raise BrokerError('gemini_connection_unknown')
        path=self.support/'profiles'/ident
        if path.is_symlink():raise BrokerError('gemini_connection_state_invalid')
        return path
    def active(self,data):
        ident=data.get('active'); entry=data['accounts'].get(ident)
        if not entry or not entry.get('signed_in'):raise BrokerError('gemini_auth_required')
        return ident,entry
    def status(self):
        try: runtime(); available=True
        except BrokerError: available=False
        data=self.read();ident=data.get('active');entry=data['accounts'].get(ident,{})
        return {'provider_status':True,'provider':'gemini','connected':bool(entry.get('signed_in')),
            'label':entry.get('label'),'runtime_available':available,
            'message':('Gemini via Antigravity · '+entry.get('label','Google account')+'.' if entry.get('signed_in') else
                       'Choose Connect account to sign in with Google, or Accounts to reconnect or add another account.')}
    def connect(self, account=None, *, mode='add', attempt_id=None, emit=lambda event:None):
        with self.operation():
            data=self.read()
            if mode=='add':
                ident='google_'+uuid.uuid4().hex
                number=data.get('next_label',len(data['accounts'])+1);data['next_label']=number+1
                entry={'label':'Google connection '+str(number),'signed_in':False,'generation':uuid.uuid4().hex}
                data['accounts'][ident]=entry;self.write(data)
            elif mode=='reauthorize' and account in data['accounts']:
                ident=account;entry=data['accounts'][ident]
                self.clear(ident)
                entry['signed_in']=False;entry['generation']=uuid.uuid4().hex
                if data.get('active')==ident:data['active']=None
                self.write(data)
            else:raise BrokerError('gemini_connection_unknown')
            emit({'event':'auth_progress','provider':'gemini','phase':'browser','message':'Finish Google sign-in in your browser.'})
            client=ACP(runtime(),self.home(ident),timeout=300)
            try:
                if 'oauth-personal' not in [a.get('id') for a in client.info.get('authMethods',[])]:raise BrokerError('gemini_google_login_unavailable')
                client.call('authenticate',{'methodId':'oauth-personal'})
                emit({'event':'auth_progress','provider':'gemini','phase':'verifying','message':'Verifying the Google connection…'})
                client.new_session()
                entry['signed_in']=True;entry['generation']=uuid.uuid4().hex;data['active']=ident;self.write(data)
                return self.status()
            finally:client.close()
    def accounts(self):
        data=self.read()
        return {'provider':'gemini','connected':bool(data.get('active')),'accounts':[
            {'registration':ident,'label':entry['label'],'signed_in':bool(entry.get('signed_in')),'active':data.get('active')==ident}
            for ident,entry in data['accounts'].items()],'pending_attempts':[]}
    def switch(self, account):
        with self.operation():
            data=self.read()
            if account not in data['accounts'] or not data['accounts'][account].get('signed_in'):raise BrokerError('gemini_auth_required')
            data['active']=account;self.write(data)
            return self.status()
    def clear(self,ident):
        client=ACP(runtime(),self.home(ident),timeout=30)
        try:
            if 'logout' not in client.info.get('agentCapabilities',{}).get('auth',{}):raise BrokerError('gemini_logout_unavailable')
            client.call('logout',{})
        finally:client.close()
    def logout(self):
        with self.operation():
            data=self.read();ident=data.get('active')
            if ident in data['accounts']:
                self.clear(ident);data['accounts'][ident]['signed_in']=False;data['accounts'][ident]['generation']=uuid.uuid4().hex
            data['active']=None;self.write(data)
            return {**self.status(),'message':'Google connection disconnected in Amua. Use Accounts to sign in again or add another account.'}
    def remove(self, account, attempt_id=None):
        with self.operation():
            data=self.read()
            if account not in data['accounts']:raise BrokerError('gemini_connection_unknown')
            self.clear(account);del data['accounts'][account]
            if data.get('active')==account:data['active']=None
            self.write(data)
            return {**self.accounts(),'removed':True,'message':'Google connection removed from Amua.'}
    def recipient(self):
        ident,entry=self.active(self.read())
        return {'provider':'gemini','registration':ident,'generation':entry['generation'],'label':entry['label']}
    def models(self): return [{'slug': 'gemini-cli-default', 'name': 'Gemini via Antigravity account default'}]
    def request(self, model, items, instructions='', emit=lambda e: None, *, idle_timeout=None):
        if model != 'gemini-cli-default': raise BrokerError('model_unavailable')
        if self.recipient() != self.approved_recipient: raise BrokerError('recipient_changed_review_again')
        blocks = [{'type': 'text', 'text': instructions + '\nReturn only the requested JSON. Do not use tools.'}]
        for item in items:
            content = item.get('content', [])
            if isinstance(content, str): content = [{'type': 'input_text', 'text': content}]
            blocks.append({'type': 'text', 'text': 'Conversation role: ' + item['role']})
            for part in content:
                if part['type'] == 'input_text': blocks.append({'type': 'text', 'text': part['text']})
                elif part['type'] == 'input_image':
                    header, data = part['image_url'].split(',', 1)
                    blocks.append({'type': 'image', 'mimeType': header[5:].split(';')[0], 'data': data})
                else: raise BrokerError('gemini_content_unsupported')
        ident,entry=self.active(self.read())
        client = ACP(runtime(), self.home(ident), timeout=idle_timeout or 180)
        try:
            if any(b['type'] == 'image' for b in blocks) and not client.info.get('agentCapabilities', {}).get('promptCapabilities', {}).get('image'):
                raise BrokerError('gemini_image_unavailable')
            client.new_session()
            result = client.call('session/prompt', {'sessionId': client.session, 'prompt': blocks}, emit)
            if result.get('stopReason') != 'end_turn': raise BrokerError('gemini_incomplete_response')
        finally: client.close()
