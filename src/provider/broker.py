#!/usr/bin/env python3
"""Amua's narrow ChatGPT-plan broker. No API keys, tools, global Codex state or shell.
JSON-lines CLI: status, connect, models, request, logout. Diagnostic errors are categories.
OAuth secrets are stored only in macOS Keychain using Security.framework.
"""
import base64
from contextlib import contextmanager
import copy
import re
import ctypes as C
try:
    import fcntl
except ImportError:
    import windows_locking as fcntl
import hashlib
import hmac
import html
import http.server
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser

AUTH = 'https://auth.openai.com'
API = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
SUPPORT = (Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local'))) / 'Amua-v2.1/provider') if sys.platform=='win32' else Path.home() / 'Library/Application Support/Amua-v2.1/provider'
MAX_BODY = 12 * 1024 * 1024
class BrokerError(Exception):
    pass

class AuthorizationError(BrokerError):
    def __init__(self,category,message,request_id=None,code=None,**extra):
        super().__init__(category)
        self.details={'category':category,'message':message,**extra}
        if isinstance(request_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{6,160}',request_id):self.details['request_id']=request_id
        if code:self.details['code']=code

class CredentialAdapter:
    def __init__(self,store):self.store=store
    def invoke(self,name,*args):
        try:return getattr(self.store,name)(*args)
        except BrokerError:raise
        except Exception:raise BrokerError('credential_store_unavailable') from None
    def read(self,account):return self.invoke('read',account)
    def write(self,account,value):return self.invoke('write',account,value)
    def delete(self,account):return self.invoke('delete',account)
    def close(self):return self.invoke('close')

def credential_store():
    if sys.platform=='win32':
        try:
            from windows_credentials import CredentialStore
            return CredentialAdapter(CredentialStore())
        except Exception:raise BrokerError('credential_store_unavailable') from None
    return Keychain()

def network_category(error):
    # Only finite categories escape; exception strings may contain private paths/URLs.
    cause=error.reason if isinstance(error,urllib.error.URLError) else error
    if isinstance(cause,(TimeoutError,socket.timeout)):return 'network_timeout'
    if isinstance(cause,socket.gaierror):return 'dns_failure'
    if isinstance(cause,ssl.SSLError):return 'tls_failure'
    if isinstance(cause,(json.JSONDecodeError,UnicodeDecodeError)):return 'provider_protocol_error'
    if isinstance(cause,ConnectionError):return 'network_connection_failure'
    return 'network_or_protocol_error'

def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')
def unb64(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
TERMINAL_REFRESH_CODES=('invalid_grant','invalid_refresh_token','token_expired','refresh_token_expired','refresh_token_invalidated','refresh_token_reused')
HTTP_CODES=set(TERMINAL_REFRESH_CODES)|{'invalid_request','invalid_client','access_denied','unauthorized_client','unsupported_grant_type','invalid_scope','invalid_resource','subscription_sharing_user_not_eligible','subscription_sharing_usage_limit_exceeded','subscription_sharing_usage_unavailable','subscription_sharing_unsupported_capability','subscription_sharing_route_not_supported','subscription_sharing_invalid_user','chatpass_v2_scope_not_authorized','chatpass_v2_invalid_authorization_context','subscription_sharing_user_unavailable'}
def http_failure(error):
    category='http_'+str(error.code);code=None;shape='unparsed';oauth_reason=None;request_id=error.headers.get('x-request-id') if error.headers else None
    try:
        payload=json.loads(error.read(16384));shape='json_object' if isinstance(payload,dict) else 'json_other'
        if isinstance(payload,dict):
            remote=payload.get('error');shape='error_object' if isinstance(remote,dict) else ('error_string' if isinstance(remote,str) else ('detail_object' if 'detail' in payload else shape))
            candidate=(remote.get('code') or remote.get('type')) if isinstance(remote,dict) else remote
            description=payload.get('error_description') or (remote.get('message') if isinstance(remote,dict) else None)
            if isinstance(description,str):
                description=description[:2048].lower()
                if 'verifier' in description or 'pkce' in description:oauth_reason='pkce_verification_failed'
                elif 'redirect' in description:oauth_reason='redirect_uri_rejected'
                elif 'already' in description and ('used' in description or 'redeemed' in description):oauth_reason='code_already_used'
                elif 'expired' in description:oauth_reason='code_expired'
                elif 'client' in description and ('mismatch' in description or 'invalid' in description):oauth_reason='client_rejected'
            if candidate in HTTP_CODES:code=candidate;category+='_'+code
            request_id=request_id or payload.get('request_id')
    except (ValueError,OSError,TypeError):pass
    message='ChatGPT could not complete this operation (HTTP '+str(error.code)+'). No different billing route was used.'
    if code=='subscription_sharing_user_not_eligible':message='ChatGPT plan usage is unavailable for this account, workspace or policy. Signing in repeatedly cannot override eligibility. Review the permitted account and workspace.'
    elif code=='subscription_sharing_usage_limit_exceeded':message='This app has reached a ChatGPT plan usage limit. Review ChatGPT Settings → Usage before trying again.'
    result=AuthorizationError(category,message,request_id,code,http_status=error.code,response_shape=shape)
    if oauth_reason:result.details['oauth_reason']=oauth_reason
    return result

def terminal_refresh_error(error):
    code=getattr(error,'details',{}).get('code')
    return code in TERMINAL_REFRESH_CODES or any(str(error)==c or str(error).startswith('http_400_'+c) or str(error).startswith('http_401_'+c) for c in TERMINAL_REFRESH_CODES)

def http_json(url, data=None, token=None, form=False):
    headers = {'Accept':'application/json'}
    if token: headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        data = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data,headers),timeout=30) as r:
            raw=r.read(MAX_BODY+1)
            if len(raw)>MAX_BODY: raise BrokerError('response_too_large')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:raise http_failure(e) from None
    except (OSError, ValueError) as error: raise BrokerError(network_category(error)) from None

class Keychain:
    """Generic password API, with secret values absent from process arguments."""
    def __init__(self):
        self.cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.sec=C.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self.cf.CFStringCreateWithCString.argtypes=[C.c_void_p,C.c_char_p,C.c_uint32];self.cf.CFStringCreateWithCString.restype=C.c_void_p
        self.cf.CFDictionaryCreate.argtypes=[C.c_void_p,C.POINTER(C.c_void_p),C.POINTER(C.c_void_p),C.c_long,C.c_void_p,C.c_void_p];self.cf.CFDictionaryCreate.restype=C.c_void_p
        self.cf.CFDataCreate.argtypes=[C.c_void_p,C.c_char_p,C.c_long];self.cf.CFDataCreate.restype=C.c_void_p
        self.cf.CFDataGetLength.argtypes=[C.c_void_p];self.cf.CFDataGetLength.restype=C.c_long
        self.cf.CFDataGetBytePtr.argtypes=[C.c_void_p];self.cf.CFDataGetBytePtr.restype=C.c_void_p
        self.cf.CFRelease.argtypes=[C.c_void_p]
        for name in ('SecItemCopyMatching','SecItemAdd','SecItemUpdate','SecItemDelete'):
            getattr(self.sec,name).argtypes=([C.c_void_p,C.c_void_p] if name!='SecItemDelete' else [C.c_void_p])
        self.owned=[]
    def const(self,name):
        return C.c_void_p.in_dll(self.sec if name.startswith('kSec') else self.cf,name).value
    def string(self,s):
        p=self.cf.CFStringCreateWithCString(None,s.encode(),0x08000100);self.owned.append(p);return p
    def dictionary(self,items):
        k=(C.c_void_p*len(items))(*[self.const(k) for k,v in items]);v=(C.c_void_p*len(items))(*[v for k,v in items])
        p=self.cf.CFDictionaryCreate(None,k,v,len(items),None,None);self.owned.append(p);return p
    def query(self,account):
        return [('kSecClass',self.const('kSecClassGenericPassword')),('kSecAttrService',self.string('local.rejie.amua.v21.chatgpt')),('kSecAttrAccount',self.string(account))]
    def read(self,account):
        q=self.dictionary(self.query(account)+[('kSecReturnData',self.const('kCFBooleanTrue')),('kSecMatchLimit',self.const('kSecMatchLimitOne'))]);result=C.c_void_p()
        status=self.sec.SecItemCopyMatching(q,C.byref(result))
        if status==-25300:return None
        if status:raise BrokerError('keychain_unavailable')
        try:return json.loads(C.string_at(self.cf.CFDataGetBytePtr(result),self.cf.CFDataGetLength(result)))
        finally:self.cf.CFRelease(result)
    def write(self,account,value):
        raw=json.dumps(value).encode();data=self.cf.CFDataCreate(None,raw,len(raw));self.owned.append(data)
        q=self.dictionary(self.query(account));attrs=self.dictionary([('kSecValueData',data)])
        status=self.sec.SecItemUpdate(q,attrs)
        if status==-25300:status=self.sec.SecItemAdd(self.dictionary(self.query(account)+[('kSecValueData',data)]),None)
        if status:raise BrokerError('keychain_unavailable')
    def delete(self,account):
        status=self.sec.SecItemDelete(self.dictionary(self.query(account)))
        if status not in (0,-25300):raise BrokerError('keychain_unavailable')
    def close(self):
        for p in reversed(self.owned):self.cf.CFRelease(p)
        self.owned=[]

def verify_identity(token,client,nonce,jwks,now=None):
    """Pinned RS256 verification (PKCS#1 v1.5, complete encoded-block comparison)."""
    now=time.time() if now is None else now
    try:
        header64,claims64,sig64=token.split('.')
        header=json.loads(unb64(header64));claims=json.loads(unb64(claims64))
        if header.get('alg')!='RS256' or header.get('crit'):raise ValueError()
        key=next(k for k in jwks['keys'] if k.get('kid')==header.get('kid') and k.get('kty')=='RSA' and k.get('use','sig')=='sig' and k.get('alg','RS256')=='RS256')
        n=int.from_bytes(unb64(key['n']),'big');e=int.from_bytes(unb64(key['e']),'big');size=(n.bit_length()+7)//8
        sig=unb64(sig64)
        if size<256 or len(sig)!=size or int.from_bytes(sig,'big')>=n:raise ValueError()
        tail=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256((header64+'.'+claims64).encode()).digest()
        expected=b'\0\1'+b'\xff'*(size-len(tail)-3)+b'\0'+tail
        actual=pow(int.from_bytes(sig,'big'),e,n).to_bytes(size,'big')
        if not hmac.compare_digest(expected,actual):raise ValueError()
        audiences=claims.get('aud',[]);audiences=[audiences] if isinstance(audiences,str) else audiences
        if claims.get('iss')!=AUTH or client not in audiences or (len(audiences)>1 and claims.get('azp')!=client):raise ValueError()
        if not isinstance(claims.get('exp'),(int,float)) or now>=claims['exp'] or claims.get('nbf',0)>now+30:raise ValueError()
        if not isinstance(claims.get('sub'),str) or not claims['sub'] or not hmac.compare_digest(str(claims.get('nonce','')),nonce):raise ValueError()
        return claims
    except (KeyError,ValueError,TypeError,StopIteration,OverflowError):raise BrokerError('identity_validation_failed') from None

def sign_in_error(error):
    """Safe, actionable diagnostics; never echo exception strings or OAuth secrets."""
    category=str(error)
    details=getattr(error,'details',{})
    code=details.get('code')
    if code=='invalid_grant' or category=='http_400_invalid_grant':
        reason={'pkce_verification_failed':'The provider reported a PKCE verification failure.','redirect_uri_rejected':'The provider rejected the callback URI.','code_already_used':'The provider reported that the code was already used.','code_expired':'The provider reported that the code expired.','client_rejected':'The provider rejected the registration.'}.get(details.get('oauth_reason'),'It may have expired or already been used.')
        return 'ChatGPT rejected the authorization code (invalid_grant). '+reason
    if category=='network_timeout':return 'The connection timed out while completing sign-in.'
    if category=='dns_failure':return 'Amua could not resolve the sign-in server address.'
    if category=='tls_failure':return 'Amua could not verify the secure connection to the sign-in server.'
    if category=='identity_validation_failed':return 'The returned sign-in identity could not be verified.'
    if category in ('keychain_unavailable','credential_store_unavailable'):return 'Amua could not save the connection in the credential store. Allow Keychain access and retry.'
    if isinstance(details.get('message'),str):return details['message']
    if category=='browser_unavailable':return 'Amua could not open the system browser. Check the default browser and try again.'
    if category=='registration_mismatch':return 'The browser did not return the expected issued registration.'
    if category in ('stale_account_or_cancelled','cancelled'):return 'This sign-in was cancelled or replaced by a newer connection operation.'
    if re.fullmatch(r'http_[0-9]{3}(?:_[a-z0-9_]+)?',category):return 'ChatGPT could not complete sign-in ('+category+').'
    return 'Amua could not complete sign-in.'

class Broker:
    def __init__(self,support=SUPPORT,keychain=None):
        self.support=Path(support);self.support.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.support.is_symlink():raise BrokerError('unsafe_support_directory')
        os.chmod(self.support,0o700)
        self.keychain=keychain if keychain is not None else credential_store();self.cancelled=threading.Event()
        self.meta_path=self.support/'registration.json'
        with self.metadata_lock():
            if self.meta_path.exists():self.meta=json.loads(self.meta_path.read_text())
            else:
                self.meta={'host_id':'urn:uuid:'+str(uuid.uuid4()),'accounts':{},'active':None,'epoch':0}
                self.save_meta()
    @contextmanager
    def credential_lock(self):
        fd=os.open(self.support/'refresh.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            yield
        finally:os.close(fd)
    @contextmanager
    def metadata_lock(self):
        fd=os.open(self.support/'auth-state.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            yield
        finally:os.close(fd)
    def reload_meta(self):
        if self.meta_path.exists():self.meta=json.loads(self.meta_path.read_text())
    def save_meta(self):
        temp=self.support/('registration-'+secrets.token_hex(8)+'.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:json.dump(self.meta,f);f.flush();os.fsync(f.fileno())
        os.replace(temp,self.meta_path)
    def profile(self,client):
        account=self.meta['accounts'][client];tokens=None if account.get('removing') else self.keychain.read(client)
        signed_in=bool(tokens)
        plan=bool(tokens and 'chatgpt.tokens.use.direct' in tokens.get('scopes',[]))
        return {'registration':client,'label':account.get('label','Connection '+hashlib.sha256(client.encode()).hexdigest()[:8]),'email':account.get('email','ChatGPT account'),'plan_enabled':plan,'signed_in':signed_in,'active':self.meta.get('active')==client}
    def status(self):
        self.reload_meta();active=self.meta.get('active');entry=self.profile(active) if active in self.meta['accounts'] else None
        return {'connected':bool(entry and entry['signed_in']),'signed_in':bool(entry and entry['signed_in']),'plan_enabled':bool(entry and entry['plan_enabled']),'account':entry['email'] if entry else None,'account_label':entry['label'] if entry else None,'registration':active,'source':'ChatGPT plan','epoch':self.meta['epoch']}
    def recipient(self):
        with self.metadata_lock():
            self.reload_meta()
            account=self.meta.get('active');entry=self.meta.get('accounts',{}).get(account,{})
            return {'registration':account,'epoch':self.meta['epoch'],'subject':entry.get('subject'),
                    'label':entry.get('label'),'email':entry.get('email')}
    def assert_recipient(self):
        expected=getattr(self,'approved_recipient',None)
        if expected is not None and self.recipient()!=expected:raise BrokerError('recipient_changed_review_again')
    def open_bound(self,request,timeout):
        # Keep account changes serialized through transmission of request bytes.
        # Release the lock after response headers, before the long SSE read.
        with self.metadata_lock():
            self.reload_meta();account=self.meta.get('active');entry=self.meta.get('accounts',{}).get(account,{})
            actual={'registration':account,'epoch':self.meta['epoch'],'subject':entry.get('subject'),
                    'label':entry.get('label'),'email':entry.get('email')}
            if getattr(self,'approved_recipient',None) is not None and actual!=self.approved_recipient:raise BrokerError('recipient_changed_review_again')
            if account!=getattr(self,'request_client',account):raise BrokerError('recipient_changed_review_again')
            return urllib.request.urlopen(request,timeout=timeout)
    def accounts(self):
        self.reload_meta()
        return {'accounts':[self.profile(client) for client in self.meta['accounts']], 'active':self.meta.get('active'),
                'pending_attempts':[{'attempt_id':attempt,'registration':value['client_id'],'label':'Unfinished registration '+attempt[:8],'verified':False} for attempt,value in self.meta.get('pending_attempts',{}).items()]}
    def switch(self,account):
        if not isinstance(account,str):raise BrokerError('invalid_account')
        with self.metadata_lock():
            self.reload_meta()
            if account not in self.meta['accounts']:raise BrokerError('unknown_account')
            if self.meta['accounts'][account].get('removing'):raise BrokerError('connection_removal_in_progress')
            tokens=self.keychain.read(account)
            if not tokens:raise AuthorizationError('reauthorization_required','Sign in again to this saved connection before switching to it.',account=account)
            if tokens.get('client_id',account)!=account or (tokens.get('subject') is not None and tokens['subject']!=self.meta['accounts'][account]['subject']):raise BrokerError('account_mismatch')
            self.cancelled.set();self.meta['active']=account;self.meta['epoch']+=1;self.save_meta()
        (self.support/'models.json').unlink(missing_ok=True)
        return self.status()
    def connect(self,account=None,emit=lambda x:None,mode='add',attempt_id=None):
        self.reload_meta()
        if mode not in ('add','reauthorize','retry'):raise BrokerError('invalid_connection_mode')
        if mode=='add':
            if account is not None or attempt_id is not None:raise BrokerError('new_registration_must_not_select_saved_account')
            issued='dynamic_agent_client';selected=None
        elif mode=='reauthorize':
            if not isinstance(account,str) or account not in self.meta['accounts'] or attempt_id is not None:raise BrokerError('unknown_account')
            issued=account;selected=self.meta['accounts'][account]
            if selected.get('removing'):raise BrokerError('connection_removal_in_progress')
        else:
            if not isinstance(attempt_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',attempt_id):raise BrokerError('unknown_pending_attempt')
            pending=self.meta.get('pending_attempts',{}).get(attempt_id)
            if account is not None or not pending:raise BrokerError('unknown_pending_attempt')
            issued=pending['client_id'];selected=None
        expected_epoch=self.meta['epoch'];expected_active=self.meta.get('active');expected_auth_revision=self.meta.get('auth_revision',0)
        attempt_id=attempt_id or str(uuid.uuid4())
        self.cancelled.clear();state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        deadline=time.monotonic()+300;result={};outer=self
        completion={};failure=[]
        def complete_callback():
            if self.cancelled.is_set():raise BrokerError('cancelled')
            if result.get('error') or result.get('error_code'):
                code=result.get('error_code') or result.get('error')
                if code=='3p_login_workspace_scope_denied':
                    raise AuthorizationError('workspace_scope_denied','This connection cannot authorize the selected account or workspace. Choose Add another account or workspace to start a new registration. Workspace policies and ChatGPT plan eligibility still apply.',result.get('request_id'),code)
                raise AuthorizationError('authorization_denied','Sign-in was declined. Your previously active connection is unchanged.',result.get('request_id'))
            client=result.get('client_id',None if mode=='add' else issued)
            if not client or client=='dynamic_agent_client' or (mode!='add' and client!=issued):raise BrokerError('registration_mismatch')
            emit({'event':'auth_progress','stage':'exchanging_code'})
            try:
                tokens=http_json(AUTH+'/api/accounts/oauth/token',{'grant_type':'authorization_code','client_id':client,'code':result.get('code',''),'code_verifier':verifier,'redirect_uri':redirect,'resource':API},form=True)
            except BrokerError as error:
                if mode!='reauthorize':
                    with self.metadata_lock():
                        self.reload_meta()
                        if self.meta.get('auth_revision',0)!=expected_auth_revision:raise BrokerError('stale_account_or_cancelled')
                        self.meta.setdefault('pending_attempts',{})[attempt_id]={'client_id':client,'created_at':time.time(),'verified':False};self.save_meta()
                    error.pending_attempt_id=attempt_id
                    detail=dict(getattr(error,'details',{}));detail.update(category=str(error),pending_attempt_id=attempt_id);detail['message']=sign_in_error(error)+' Choose Retry sign-in to get a fresh authorization for this registration, or add another account or workspace. Your prior active connection is unchanged.';error.details=detail
                raise
            emit({'event':'auth_progress','stage':'verifying_identity'})
            identity=verify_identity(tokens.get('id_token',''),client,nonce,http_json(AUTH+'/.well-known/jwks.json'))
            if selected and selected['subject']!=identity['sub']:raise BrokerError('account_mismatch')
            scopes=tokens.get('scope','').split();plan_enabled='chatgpt.tokens.use.direct' in scopes
            tokens.update(client_id=client,subject=identity['sub'],expires_at=time.time()+tokens.get('expires_in',0),scopes=scopes)
            emit({'event':'auth_progress','stage':'saving_connection'})
            with self.credential_lock():
                with self.metadata_lock():
                    self.reload_meta()
                    if self.cancelled.is_set() or self.meta['epoch']!=expected_epoch or self.meta.get('active')!=expected_active or self.meta.get('auth_revision',0)!=expected_auth_revision:raise BrokerError('stale_account_or_cancelled')
                    existing=self.meta['accounts'].get(client)
                    if existing and existing['subject']!=identity['sub']:raise BrokerError('account_mismatch')
                    self.keychain.write(client,tokens)
                    if existing:label=existing.get('label','Connection '+hashlib.sha256(client.encode()).hexdigest()[:8])
                    else:
                        sequence=self.meta.get('registration_sequence',len(self.meta['accounts']))+1;self.meta['registration_sequence']=sequence;label='Connection '+str(sequence)
                    self.meta.setdefault('pending_attempts',{}).pop(attempt_id,None)
                    self.meta['accounts'][client]={'subject':identity['sub'],'email':identity.get('email','ChatGPT account'),'label':label,'plan_enabled':plan_enabled}
                    self.meta['active']=client;self.meta['epoch']+=1;self.save_meta()
            (self.support/'models.json').unlink(missing_ok=True)
            return self.status()
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def setup(self):
                super().setup();self.connection.settimeout(5)
            def do_GET(self):
                q=urllib.parse.urlsplit(self.path);params=urllib.parse.parse_qs(q.query)
                valid=q.path=='/auth/callback' and self.client_address[0]=='127.0.0.1' and params.get('state')==[state] and not result and time.monotonic()<deadline and not outer.cancelled.is_set()
                if not valid:self.send_error(400,'Invalid or expired callback');return
                if any(len(params.get(k,[]))>1 for k in ('code','client_id','error','error_code','request_id')):self.send_error(400);return
                if not params.get('code') and not params.get('error') and not params.get('error_code'):self.send_error(400,'Missing authorization result');return
                result.update({k:v[0] for k,v in params.items()})
                emit({'event':'auth_progress','stage':'callback_received'})
                try:
                    completion.update(complete_callback())
                    message='Connected to ChatGPT. Return to Amua.' if completion.get('plan_enabled') else 'Signed in. ChatGPT plan access is unavailable for this connection. Return to Amua.'
                    title='Amua sign-in complete'
                except Exception as error:
                    failure.append(error)
                    message=sign_in_error(error)+' Return to Amua to review the error and retry sign-in.'
                    title='Amua sign-in did not finish'
                page=('''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'''+title+'''</title></head><body style="font:17px system-ui,sans-serif;line-height:1.6;max-width:38rem;margin:12vh auto;padding:24px;color:#243248"><h1>'''+title+'''</h1><p>'''+html.escape(message)+'''</p></body></html>''').encode()
                try:
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'");self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page)
                except OSError:pass # Closing the browser must not undo a completed connection.

        server=http.server.HTTPServer(('127.0.0.1',0),Handler);server.timeout=.2
        redirect='http://127.0.0.1:'+str(server.server_port)+'/auth/callback'
        params={'client_id':issued,'ext_agent_host_id':self.meta['host_id'],'response_type':'code','redirect_uri':redirect,'scope':SCOPES,'resource':API,'state':state,'nonce':nonce,'code_challenge_method':'S256','code_challenge':b64(hashlib.sha256(verifier.encode()).digest())}
        if mode=='add':params['agent_name_hint']='Amua'
        elif mode=='reauthorize':
            saved=self.keychain.read(account)
            if saved and saved.get('id_token'):params['id_token_hint']=saved['id_token']
            if selected.get('email'):params['login_hint']=selected['email']
        url=AUTH+'/api/accounts/authorize?'+urllib.parse.urlencode(params)
        emit({'event':'browser_consent_required','expires_seconds':300,'mode':mode})
        browser_result={}
        def open_browser():
            try:
                if webbrowser.open(url) is False:browser_result['failed']=True
            except Exception:browser_result['failed']=True
        # A browser controller may wait for navigation/Apple Events to complete.
        # Redeem the one-use code immediately, even while that controller waits.
        opener=threading.Thread(target=open_browser,daemon=True,name='Amua-browser-open')
        try:
            opener.start()
            while not result and time.monotonic()<deadline and not self.cancelled.is_set():
                if browser_result.get('failed'):raise BrokerError('browser_unavailable')
                server.handle_request()
        finally:server.server_close()
        if failure:raise failure[0]
        if self.cancelled.is_set():raise BrokerError('cancelled')
        if not result:raise BrokerError('authorization_expired')
        return completion
    def credentials(self):
        client=self.meta.get('active');expected_epoch=self.meta['epoch']
        if not client:raise BrokerError('not_connected')
        # Cross-process lock covers rotating token refresh and use of latest record.
        lock=os.open(self.support/'refresh.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(lock,fcntl.LOCK_EX)
            current=json.loads(self.meta_path.read_text())
            if current.get('active')!=client or current.get('epoch')!=expected_epoch:raise BrokerError('stale_account_or_cancelled')
            tokens=self.keychain.read(client)
            if not tokens:raise BrokerError('not_connected')
            if 'chatgpt.tokens.use.direct' not in tokens.get('scopes',[]):raise AuthorizationError('plan_permission_missing','Signed in, but ChatGPT plan usage is not enabled for this connection. Reauthorize this saved connection and review the requested permission. Eligibility and workspace policies may still restrict access.')
            if tokens.get('expires_at',0)<time.time()+60:
                try:
                    fresh=http_json(AUTH+'/api/accounts/oauth/token',{'grant_type':'refresh_token','client_id':client,'refresh_token':tokens['refresh_token'],'resource':API},form=True)
                except BrokerError as error:
                    if not terminal_refresh_error(error):raise
                    with self.metadata_lock():
                        self.reload_meta()
                        if self.meta.get('active')!=client or self.meta['epoch']!=expected_epoch:raise BrokerError('stale_account_or_cancelled')
                        self.keychain.delete(client);self.meta['accounts'][client]['plan_enabled']=False;self.meta['epoch']+=1;self.save_meta()
                    (self.support/'models.json').unlink(missing_ok=True)
                    raise AuthorizationError('reauthorization_required','This saved connection has expired or was disconnected. Sign in again to this saved connection. Other saved accounts were not signed out.',account=client) from None
                tokens.update(fresh);tokens['expires_at']=time.time()+fresh.get('expires_in',0)
                if 'scope' in fresh:tokens['scopes']=fresh['scope'].split()
                current=json.loads(self.meta_path.read_text())
                if current.get('active')!=client or current.get('epoch')!=self.meta['epoch']:raise BrokerError('stale_account_or_cancelled')
                self.keychain.write(client,tokens)
            if 'chatgpt.tokens.use.direct' not in tokens.get('scopes',[]):raise BrokerError('plan_permission_missing')
            return tokens
        finally:os.close(lock)
    def models(self):
        self.assert_recipient()
        data=http_json(API+'/models',token=self.credentials()['access_token'])
        self.assert_recipient()
        models=[{'slug':m['slug'],'display_name':m['display_name']} for m in data.get('models',[]) if m.get('visibility')=='list']
        path=self.support/'models.json';temp=self.support/('models-'+secrets.token_hex(8)+'.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:json.dump(models,f);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
        return models
    def request(self,model,items,instructions='',emit=lambda x:None,*,idle_timeout=None):
        self.cancelled.clear();epoch=self.meta['epoch'];client=self.meta['active']
        self.request_client=client;self.assert_recipient()
        validate_input(model,items,instructions)
        raw=json.dumps({'model':model,'input':items,'instructions':instructions,'store':False,'stream':True}).encode()
        if len(raw)>MAX_BODY:raise BrokerError('request_too_large')
        req=urllib.request.Request(API+'/responses',raw,{'Content-Type':'application/json','Authorization':'Bearer '+self.credentials()['access_token'],'Accept':'text/event-stream'})
        watch=None
        if idle_timeout is not None:
            from progress_watch import ProgressWatch,ProgressStalled
            try:watch=ProgressWatch(idle_timeout)
            except ValueError:raise BrokerError('invalid_model_wait_time') from None
        done=False;total=0
        try:
            with self.open_bound(req,timeout=idle_timeout if watch else 30) as r:
                event=[]
                for line in r:
                    if watch:watch.check()
                    if self.cancelled.is_set():raise BrokerError('cancelled')
                    total+=len(line)
                    if total>MAX_BODY:raise BrokerError('response_too_large')
                    if len(line)>1024*1024:raise BrokerError('event_too_large')
                    line=line.decode('utf-8').rstrip('\r\n')
                    if line.startswith('data:'):event.append(line[5:].strip())
                    elif not line and event:
                        body='\n'.join(event);event=[]
                        if body=='[DONE]':continue
                        data=json.loads(body);kind=data.get('type','')
                        if kind in ('response.failed','response.incomplete','error'):raise BrokerError('inference_'+kind.replace('.','_'))
                        if kind=='response.output_text.delta':
                            if not isinstance(data.get('delta',''),str):raise BrokerError('invalid_stream_delta')
                            emit({'event':'delta','text':data.get('delta','')})
                        if watch:
                            metadata=watch.accept(data)
                            if metadata:emit(metadata)
                        if kind=='response.completed':done=True;break
        except urllib.error.HTTPError as e:raise http_failure(e) from None
        except (OSError,ValueError) as error:
            category=network_category(error)
            raise BrokerError('model_chat_stalled' if watch and category=='network_timeout' else category) from None
        except Exception as error:
            if watch and isinstance(error,ProgressStalled):raise BrokerError('model_chat_stalled') from None
            raise
        current=json.loads(self.meta_path.read_text())
        if self.cancelled.is_set() or epoch!=current['epoch'] or client!=current['active']:raise BrokerError('stale_account_or_cancelled')
        if not done:raise BrokerError('stream_interrupted')
        return {'completed':True,'epoch':epoch,'model':model}
    def remove(self,account=None,attempt_id=None):
        if (account is None)==(attempt_id is None):raise BrokerError('select_one_connection_to_remove')
        if account is not None and (not isinstance(account,str) or not account):raise BrokerError('invalid_account')
        if attempt_id is not None and (not isinstance(attempt_id,str) or not attempt_id):raise BrokerError('unknown_pending_attempt')
        if attempt_id is not None:
            with self.credential_lock():
                with self.metadata_lock():
                    self.reload_meta();pending=self.meta.get('pending_attempts',{}).get(attempt_id)
                    if pending is None:raise BrokerError('unknown_pending_attempt')
                    client=pending['client_id'];self.meta['pending_attempts'].pop(attempt_id)
                    if self.meta.get('pending_client')==client:self.meta.pop('pending_client',None)
                    self.meta['auth_revision']=self.meta.get('auth_revision',0)+1;self.save_meta()
            return {**self.accounts(),**self.status(),'removed':True,'removed_attempt_id':attempt_id,'remote_revocation_attempted':False,'remote_revocation_confirmed':None,'message':'Unfinished registration removed locally. Saved connections were not signed out.'}
        confirmed=None;attempted=False;active_removed=False
        with self.credential_lock():
            with self.metadata_lock():
                self.reload_meta()
                if account not in self.meta['accounts']:raise BrokerError('unknown_account')
                tokens=self.keychain.read(account)
                if tokens and tokens.get('client_id',account)!=account:raise BrokerError('account_mismatch')
                active_removed=self.meta.get('active')==account
                if active_removed:self.cancelled.set();self.meta['active']=None;self.meta['epoch']+=1
                self.meta['accounts'][account]['removing']=True
                self.meta['auth_revision']=self.meta.get('auth_revision',0)+1;self.save_meta()
            # Hold the credential lock, but never the metadata lock during network I/O.
            if tokens and tokens.get('refresh_token'):
                attempted=True;confirmed=False
                try:
                    discovery=http_json(AUTH+'/.well-known/openid-configuration');endpoint=discovery['revocation_endpoint']
                    if not isinstance(endpoint,str) or not endpoint.startswith(AUTH+'/'):raise BrokerError('invalid_revocation_endpoint')
                    http_json(endpoint,{'token':tokens['refresh_token'],'token_type_hint':'refresh_token','client_id':account},form=True)
                    confirmed=True
                except (BrokerError,KeyError,TypeError):pass
            try:self.keychain.delete(account)
            except Exception:
                raise AuthorizationError('connection_removal_incomplete','The connection could not be fully removed because its saved credentials could not be cleared. Unlock macOS Keychain and try removing it again.') from None
            with self.metadata_lock():
                self.reload_meta();self.meta['accounts'].pop(account,None)
                self.meta['pending_attempts']={key:value for key,value in self.meta.get('pending_attempts',{}).items() if value.get('client_id')!=account}
                if self.meta.get('pending_client')==account:self.meta.pop('pending_client',None)
                # Also invalidate sign-in attempts started while removal was in progress.
                self.meta['auth_revision']=self.meta.get('auth_revision',0)+1;self.save_meta()
        if active_removed:(self.support/'models.json').unlink(missing_ok=True)
        message='Saved connection removed locally.'
        if attempted and not confirmed:message+=' Remote sign-out was not confirmed. You can disconnect the app in ChatGPT Settings.'
        return {**self.accounts(),**self.status(),'removed':True,'removed_registration':account,'active_removed':active_removed,'remote_revocation_attempted':attempted,'remote_revocation_confirmed':confirmed,'message':message}
    def logout(self):
        self.cancelled.set();confirmed=True
        with self.metadata_lock():
            self.reload_meta();client=self.meta.get('active')
            self.meta['active']=None;self.meta['epoch']+=1;self.save_meta()
        (self.support/'models.json').unlink(missing_ok=True)
        if client:
            tokens=self.keychain.read(client)
            if tokens and tokens.get('refresh_token'):
                try:
                    discovery=http_json(AUTH+'/.well-known/openid-configuration')
                    endpoint=discovery['revocation_endpoint']
                    if not endpoint.startswith(AUTH+'/'):raise BrokerError('invalid_revocation_endpoint')
                    http_json(endpoint,{'token':tokens['refresh_token'],'token_type_hint':'refresh_token','client_id':client},form=True)
                except BrokerError:confirmed=False
            lock=os.open(self.support/'refresh.lock',os.O_CREAT|os.O_RDWR,0o600)
            try:
                fcntl.flock(lock,fcntl.LOCK_EX);self.keychain.delete(client)
            finally:os.close(lock)
        return {'signed_out':True,'remote_revocation_confirmed':confirmed}

def validate_input(model,items,instructions):
    if not isinstance(model,str) or not model or len(model)>100:raise BrokerError('invalid_model')
    if not isinstance(instructions,str) or len(instructions)>128000:raise BrokerError('invalid_instructions')
    if not isinstance(items,list) or not items or len(items)>100:raise BrokerError('invalid_input')
    for item in items:
        if not isinstance(item,dict) or set(item)-{'role','content'} or item.get('role') not in ('user','assistant','developer'):raise BrokerError('invalid_message')
        content=item.get('content')
        if isinstance(content,str):continue
        if not isinstance(content,list):raise BrokerError('invalid_content')
        for part in content:
            if not isinstance(part,dict):raise BrokerError('invalid_content')
            if part.get('type')=='input_text' and set(part)=={'type','text'} and isinstance(part['text'],str):continue
            if part.get('type')=='input_image' and set(part)<= {'type','image_url','detail'} and isinstance(part.get('image_url'),str) and part['image_url'].startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):continue
            raise BrokerError('unsupported_content')

def main():
    def emit(event):print(json.dumps(event),flush=True)
    broker=Broker()
    for line in sys.stdin:
        try:
            if len(line)>MAX_BODY:raise BrokerError('request_too_large')
            command=json.loads(line);action=command.get('action')
            if action=='status':result=broker.status()
            elif action=='connect':result=broker.connect(command.get('account'),emit,command.get('mode','add'),command.get('attempt_id'))
            elif action in ('accounts','accounts/list'):result=broker.accounts()
            elif action=='switch':result=broker.switch(command.get('account'))
            elif action=='remove':result=broker.remove(command.get('account'),command.get('attempt_id'))
            elif action=='models':result=broker.models()
            elif action=='request':result=broker.request(command['model'],command['input'],command.get('instructions',''),emit)
            elif action=='logout':result=broker.logout()
            else:raise BrokerError('unknown_action')
            emit({'event':'result','result':result})
        except BrokerError as e:emit({'event':'error',**getattr(e,'details',{'category':str(e)})})
        except Exception:emit({'event':'error','category':'internal_error'})
    broker.keychain.close()
if __name__=='__main__':main()
