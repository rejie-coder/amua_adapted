"""Google's bundled CLI over ACP; isolated Google login, no API billing or agent tools."""
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
from broker import BrokerError, SUPPORT

MAX_LINE = 2_000_000
SETTINGS = {
    'security': {'auth': {'selectedType': 'oauth-personal'}, 'disableYoloMode': True},
    'tools': {'core': ['__amua_no_agent_tools__']},
    'mcpServers': {}, 'mcp': {'allowed': []},
    'hooks': {}, 'hooksConfig': {'enabled': False},
    'context': {'fileName': '__amua_no_context__'},
    'telemetry': {'enabled': False, 'logPrompts': False},
    'privacy': {'usageStatisticsEnabled': False},
    'general': {'enableAutoUpdate': False},
    'advanced': {'ignoreLocalEnv': True},
}


def runtime():
    root = Path(__file__).resolve().parent
    node = root / 'gemini/node.exe'
    cli = root / 'gemini/package/bundle/gemini.js'
    if not node.is_file() or not cli.is_file():
        raise BrokerError('gemini_runtime_missing')
    return [str(node), str(cli), '--acp']


def environment(home, settings):
    # No inherited API keys, OAuth overrides, Node injection, proxy or Cloud billing.
    allow = {'PATH', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'WINDIR', 'TEMP', 'TMP',
             'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'HOME', 'LANG'}
    env = {k: v for k, v in os.environ.items() if k in allow}
    env.update({'GEMINI_CLI_HOME': str(home), 'GEMINI_CLI_SYSTEM_SETTINGS_PATH': str(settings),
                'GEMINI_CLI_SYSTEM_DEFAULTS_PATH': str(settings),
                'GEMINI_CLI_SURFACE': 'amua', 'GEMINI_TELEMETRY_ENABLED': 'false',
                'NO_COLOR': '1'})
    return env


class ACP:
    def __init__(self, command, home, timeout=180):
        home.mkdir(parents=True, exist_ok=True)
        self.cwd = home / 'empty-workspace'; self.cwd.mkdir(exist_ok=True)
        settings = home / 'amua-settings.json'
        settings.write_text(json.dumps(SETTINGS), encoding='utf-8')
        self.timeout = timeout; self.seq = 0; self.events = queue.Queue(maxsize=128)
        self.session = None; self.closed = False
        # Every descendant belongs to a kill-on-close job, including forced UI Stop.
        if sys.platform == 'win32':
            from windows_process import limit_current_process
            limit_current_process()
        self.p = subprocess.Popen(command, cwd=self.cwd, env=environment(home, settings),
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL,
                                  creationflags=0x08000000 if sys.platform == 'win32' else 0)
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.info = self.call('initialize', {'protocolVersion': 1,
                'clientInfo': {'name': 'amua', 'version': '3.3.0'},
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
                if 'error' in event: raise BrokerError('gemini_auth_required' if event['error'].get('code') == -32000 else 'gemini_request_failed')
                if method=='authenticate' and event.get('result') is None:return {}
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
            self.p.terminate()
            try: self.p.wait(timeout=3)
            except subprocess.TimeoutExpired: self.p.kill(); self.p.wait(timeout=3)
        for pipe in (self.p.stdin, self.p.stdout):
            try: pipe.close()
            except OSError: pass


class GeminiBroker:
    def __init__(self):
        self.support = SUPPORT / 'gemini'; self.support.mkdir(parents=True, exist_ok=True)
        self.marker = self.support / 'connection.json'; self.keychain = self
        self.approved_recipient = None
    def close(self): pass
    def status(self):
        try: runtime(); available = True
        except BrokerError: available = False
        return {'provider_status': True, 'provider': 'gemini', 'connected': self.marker.exists(),
                'runtime_available': available,
                'message': 'Gemini uses Google sign-in in an isolated Amua profile. Account quota and eligibility are checked by Google. Live subscription acceptance is still required.'}
    def connect(self, *args, **kwargs):
        client = ACP(runtime(), self.support / 'profile', timeout=300)
        try:
            if 'oauth-personal' not in [a.get('id') for a in client.info.get('authMethods', [])]: raise BrokerError('gemini_google_login_unavailable')
            client.call('authenticate', {'methodId': 'oauth-personal'})
            client.new_session()
            self.marker.write_text(json.dumps({'registration': str(uuid.uuid4())}), encoding='utf-8')
            return self.status()
        finally: client.close()
    def accounts(self): return self.status()
    def logout(self):
        # Disable this Amua connection; do not claim remote token revocation.
        self.marker.unlink(missing_ok=True)
        return {**self.status(), 'message': 'Gemini disabled in Amua. Google sign-in remains cached in the dedicated CLI profile; revoke access in your Google account to sign out remotely.'}
    def recipient(self):
        if not self.marker.exists(): raise BrokerError('gemini_auth_required')
        return {'provider': 'gemini', 'registration': json.loads(self.marker.read_text())['registration'],
                'label': 'Google account in Amua Gemini profile'}
    def models(self): return [{'slug': 'gemini-cli-default', 'name': 'Gemini CLI account default'}]
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
        client = ACP(runtime(), self.support / 'profile', timeout=idle_timeout or 180)
        try:
            if any(b['type'] == 'image' for b in blocks) and not client.info.get('agentCapabilities', {}).get('promptCapabilities', {}).get('image'):
                raise BrokerError('gemini_image_unavailable')
            client.new_session()
            result = client.call('session/prompt', {'sessionId': client.session, 'prompt': blocks}, emit)
            if result.get('stopReason') != 'end_turn': raise BrokerError('gemini_incomplete_response')
        finally: client.close()
