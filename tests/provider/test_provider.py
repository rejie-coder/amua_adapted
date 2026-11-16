import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import socket
import ssl
import tempfile
import time
import threading
import urllib.parse
import urllib.request
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/provider'))
import os,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platform_privacy import assert_private_file
OPENSSL=shutil.which('openssl') or str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Git/usr/bin/openssl.exe')
import broker
import provider_helper
class MemoryKeys:
    def __init__(self):self.data={}
    def read(self,k):return self.data.get(k)
    def write(self,k,v):self.data[k]=dict(v)
    def delete(self,k):self.data.pop(k,None)
    def close(self):pass
class Stream(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()));self.keys=MemoryKeys();self.b=broker.Broker(self.temp.name,self.keys)
    def tearDown(self):self.temp.cleanup()
    def ready(self):
        self.b.meta.update(active='oaiapp_test');self.b.meta['accounts']['oaiapp_test']={'subject':'test','email':'synthetic@example.invalid'};self.b.save_meta()
        self.keys.write('oaiapp_test',{'access_token':'synthetic','refresh_token':'synthetic','expires_at':time.time()+3600,'scopes':['chatgpt.tokens.use.direct']})
    def test_offline_disconnected(self):
        self.assertFalse(self.b.status()['connected'])
        with self.assertRaisesRegex(broker.BrokerError,'not_connected'):self.b.models()
    def test_host_stable_and_permissions(self):
        again=broker.Broker(self.temp.name,self.keys)
        self.assertEqual(self.b.meta['host_id'],again.meta['host_id']);assert_private_file(self,Path(self.temp.name)/'registration.json')
    def test_keychain_unavailable_no_fallback(self):
        self.ready()
        with patch.object(self.keys,'read',side_effect=broker.BrokerError('keychain_unavailable')):
            with self.assertRaisesRegex(broker.BrokerError,'keychain_unavailable'):self.b.credentials()
        self.assertNotIn('synthetic', (Path(self.temp.name)/'registration.json').read_text().replace('synthetic@example.invalid',''))
    def test_tool_and_remote_image_rejected(self):
        invalid=[{'role':'user','content':[{'type':'input_image','image_url':'https://example.invalid/x.png'}]}]
        with self.assertRaises(broker.BrokerError):broker.validate_input('m',invalid,'')
        with self.assertRaises(broker.BrokerError):broker.validate_input('m',[{'role':'user','content':'x','tools':['shell']}],'')
    def test_request_terminal_completion_required(self):
        self.ready();body=b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n'
        with patch.object(broker.urllib.request,'urlopen',return_value=Stream(body)):
            with self.assertRaisesRegex(broker.BrokerError,'stream_interrupted'):self.b.request('m',[{'role':'user','content':'x'}])
    def test_request_completion_and_minimal_capabilities(self):
        self.ready();seen=[]
        def open_(req,timeout):
            body=json.loads(req.data);self.assertEqual(set(body),{'model','input','instructions','store','stream'});self.assertFalse(body['store']);self.assertTrue(body['stream']);self.assertNotIn('tools',body)
            return Stream(b'data: {"type":"response.output_text.delta","delta":"hello"}\n\ndata: {"type":"response.completed"}\n\n')
        with patch.object(broker.urllib.request,'urlopen',side_effect=open_):self.assertTrue(self.b.request('m',[{'role':'user','content':'x'}],emit=seen.append)['completed'])
        self.assertEqual(seen,[{'event':'delta','text':'hello'}])
    def test_failure_after_delta_not_success(self):
        self.ready()
        with patch.object(broker.urllib.request,'urlopen',return_value=Stream(b'data: {"type":"response.output_text.delta","delta":"hello"}\n\ndata: {"type":"response.failed"}\n\n')):
            with self.assertRaisesRegex(broker.BrokerError,'inference_response_failed'):self.b.request('m',[{'role':'user','content':'x'}])
    def test_epoch_change_rejects_completed(self):
        self.ready()
        def open_(*args,**kwargs):
            self.b.meta['epoch']+=1;self.b.save_meta();return Stream(b'data: {"type":"response.completed"}\n\n')
        with patch.object(broker.urllib.request,'urlopen',side_effect=open_):
            with self.assertRaisesRegex(broker.BrokerError,'stale_account'):self.b.request('m',[{'role':'user','content':'x'}])
    def test_refresh_rotates_and_retains_scope(self):
        self.ready();self.keys.data['oaiapp_test']['expires_at']=0
        with patch.object(broker,'http_json',return_value={'access_token':'replacement','refresh_token':'rotated','expires_in':3600}) as call:
            self.assertEqual(self.b.credentials()['refresh_token'],'rotated');self.assertEqual(call.call_args.args[1]['client_id'],'oaiapp_test');self.assertNotIn('scope',call.call_args.args[1])
    def test_logout_remote_failure_clears_local(self):
        self.ready()
        with patch.object(broker,'http_json',side_effect=broker.BrokerError('offline')):
            r=self.b.logout();self.assertFalse(r['remote_revocation_confirmed']);self.assertFalse(self.b.status()['connected']);self.assertEqual(self.keys.data,{})
    def test_selection_rejects_symlink_and_workbook_without_digest(self):
        f=Path(self.temp.name)/'test.png';f.write_bytes(b'fake');link=Path(self.temp.name)/'link.png';link.symlink_to(f)
        with self.assertRaisesRegex(broker.BrokerError,'selection_changed'):provider_helper.prepare({'text':'x','paths':[str(link)]})
        f=Path(self.temp.name)/'test.xlsx';f.write_bytes(b'fake')
        with self.assertRaisesRegex(broker.BrokerError,'derive_workbook'):provider_helper.prepare({'text':'x','paths':[str(f)]})
    def test_selected_png_and_digest_inputs(self):
        f=Path(self.temp.name)/'test.png';f.write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+(1).to_bytes(4,'big')*2)
        r=provider_helper.prepare({'text':'x','paths':[str(f)],'project':{'untrusted':'ignore system'}})
        self.assertEqual(r[0]['content'][-1]['type'],'input_image');broker.validate_input('m',r,'')
    def test_nested_source_paths_exact_verification(self):
        import hashlib
        first=Path(self.temp.name)/'first';second=Path(self.temp.name)/'second';first.mkdir();second.mkdir()
        a=first/'one.txt';b=second/'two.txt';a.write_text('one');b.write_text('two')
        expected=[{'id':'source1','name':a.name,'sha256':hashlib.sha256(a.read_bytes()).hexdigest()},{'id':'source2','name':b.name,'sha256':hashlib.sha256(b.read_bytes()).hexdigest()}]
        command={'text':'analyze','paths':[self.temp.name],'source_paths':[str(a),str(b)],'project':{'derived':'test'},'expected_sources':expected}
        result=provider_helper.prepare(command)
        wire=json.dumps(result);self.assertNotIn(str(a),wire);self.assertNotIn(str(b),wire);self.assertNotIn('source_paths',wire)
        command['source_paths']=[str(a)]
        with self.assertRaisesRegex(broker.BrokerError,'source_manifest_changed'):provider_helper.prepare(command)
        command['source_paths']=[str(a),str(b)];b.write_text('changed')
        with self.assertRaisesRegex(broker.BrokerError,'source_manifest_changed'):provider_helper.prepare(command)
    def test_source_paths_empty_symlink_and_limit_fail_closed(self):
        command={'text':'analyze','source_paths':[],'project':{},'expected_sources':[{'name':'missing','sha256':'x'}]}
        with self.assertRaisesRegex(broker.BrokerError,'source_manifest_changed'):provider_helper.prepare(command)
        command['source_paths']=['x']*10001
        with self.assertRaisesRegex(broker.BrokerError,'invalid_source_paths'):provider_helper.prepare(command)
        f=Path(self.temp.name)/'file.txt';f.write_text('x');link=Path(self.temp.name)/'link.txt';link.symlink_to(f);command['source_paths']=[str(link)]
        with self.assertRaisesRegex(broker.BrokerError,'selection_changed'):provider_helper.prepare(command)
    def test_finite_network_categories_no_private_exception_text(self):
        cases=[(TimeoutError('private timeout URL'),'network_timeout'),(socket.gaierror(-2,'private host'),'dns_failure'),(ssl.SSLError('private certificate URL'),'tls_failure'),(ConnectionResetError('private peer'),'network_connection_failure'),(json.JSONDecodeError('private document','x',0),'provider_protocol_error'),(OSError('private path'),'network_or_protocol_error')]
        for error,expected in cases:
            self.assertEqual(broker.network_category(error),expected)
            wrapped=broker.urllib.error.URLError(error)
            with patch.object(broker.urllib.request,'urlopen',side_effect=wrapped):
                with self.assertRaises(broker.BrokerError) as caught:broker.http_json('https://example.invalid/synthetic')
            self.assertEqual(str(caught.exception),expected);self.assertNotIn('private',str(caught.exception))
    def test_stream_protocol_error_and_timeout_are_distinct(self):
        self.ready()
        for error,expected in [(TimeoutError('private timeout'),'network_timeout'),(ssl.SSLError('private certificate'),'tls_failure')]:
            with patch.object(broker.urllib.request,'urlopen',side_effect=error):
                with self.assertRaisesRegex(broker.BrokerError,expected):self.b.request('m',[{'role':'user','content':'x'}])
        with patch.object(broker.urllib.request,'urlopen',return_value=Stream(b'data: invalid-json\n\n')):
            with self.assertRaisesRegex(broker.BrokerError,'provider_protocol_error'):self.b.request('m',[{'role':'user','content':'x'}])
    def test_image_change_between_manifest_verification_and_send_rejected(self):
        import hashlib
        f=Path(self.temp.name)/'selected.png';original=b'\x89PNG\r\n\x1a\n'+b'\0'*8+(1).to_bytes(4,'big')*2
        f.write_bytes(original);expected=[{'name':f.name,'sha256':hashlib.sha256(original).hexdigest()}]
        real_open=broker.os.open;opens=[]
        def changed_open(path,flags,*args):
            if str(path)==str(f):
                opens.append(1)
                if len(opens)==2:f.write_bytes(original+b'changed')
            return real_open(path,flags,*args)
        with patch.object(provider_helper.os,'open',side_effect=changed_open):
            with self.assertRaisesRegex(broker.BrokerError,'source_manifest_changed'):
                provider_helper.prepare({'text':'inspect','source_paths':[str(f)],'expected_sources':expected,'project':{}})
    def callback_flow(self,extra):
        launched=[];errors=[]
        def browser(url):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query);launched.append(query)
            def callback():
                try:
                    callback_url=query['redirect_uri'][0]+'?'+urllib.parse.urlencode({'state':query['state'][0],**extra})
                    urllib.request.urlopen(callback_url,timeout=3).read()
                except Exception as error:errors.append(type(error).__name__)
            threading.Thread(target=callback,daemon=True).start();return True
        return browser,launched,errors
    def test_callback_denial_does_not_exchange(self):
        browser,launched,errors=self.callback_flow({'error':'access_denied'})
        with patch.object(broker.webbrowser,'open',side_effect=browser),patch.object(broker,'http_json') as network:
            with self.assertRaisesRegex(broker.BrokerError,'authorization_denied'):self.b.connect()
            network.assert_not_called()
        self.assertFalse(self.b.status()['connected']);self.assertEqual(errors,[])
    def test_callback_missing_issued_id_rejected(self):
        browser,launched,errors=self.callback_flow({'code':'synthetic-code'})
        with patch.object(broker.webbrowser,'open',side_effect=browser),patch.object(broker,'http_json') as network:
            with self.assertRaisesRegex(broker.BrokerError,'registration_mismatch'):self.b.connect()
            network.assert_not_called()
    def test_callback_pkce_exact_uri_and_activation(self):
        browser,launched,errors=self.callback_flow({'code':'synthetic-code','client_id':'oaiapp_new'})
        def network(url,data=None,form=False):
            if 'oauth/token' in url:
                self.assertEqual(data['redirect_uri'],launched[0]['redirect_uri'][0])
                self.assertEqual(broker.b64(broker.hashlib.sha256(data['code_verifier'].encode()).digest()),launched[0]['code_challenge'][0])
                self.assertEqual(data['client_id'],'oaiapp_new');self.assertTrue(form)
                return {'access_token':'synthetic','id_token':'synthetic','expires_in':3600,'scope':'chatgpt.tokens.use.direct'}
            return {'keys':[]}
        with patch.object(broker.webbrowser,'open',side_effect=browser),patch.object(broker,'http_json',side_effect=network),patch.object(broker,'verify_identity',return_value={'sub':'new','email':'new@example.invalid'}):
            self.assertTrue(self.b.connect()['connected'])
        self.assertEqual(self.b.meta['active'],'oaiapp_new');self.assertEqual(errors,[])
    def test_identity_signed_and_tampered(self):
        key=Path(self.temp.name)/'key.pem'
        subprocess.run([OPENSSL,'genrsa','-out',str(key),'2048'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        modulus=subprocess.check_output([OPENSSL,'rsa','-in',str(key),'-modulus','-noout'],stderr=subprocess.DEVNULL).decode().strip().split('=')[1]
        jwks={'keys':[{'kid':'test','kty':'RSA','n':broker.b64(bytes.fromhex(modulus)),'e':broker.b64((65537).to_bytes(3,'big'))}]}
        def token(claims):
            signed=broker.b64(json.dumps({'alg':'RS256','kid':'test'}).encode())+'.'+broker.b64(json.dumps(claims).encode())
            signature=subprocess.check_output([OPENSSL,'dgst','-sha256','-sign',str(key)],input=signed.encode());return signed+'.'+broker.b64(signature)
        claims={'iss':broker.AUTH,'aud':'client','sub':'user','exp':time.time()+100,'nonce':'nonce'};valid=token(claims)
        self.assertEqual(broker.verify_identity(valid,'client','nonce',jwks)['sub'],'user')
        for client,nonce,now in [('other','nonce',None),('client','wrong',None),('client','nonce',time.time()+200)]:
            with self.assertRaises(broker.BrokerError):broker.verify_identity(valid,client,nonce,jwks,now)
        parts=valid.split('.');parts[1]=broker.b64(json.dumps({**claims,'sub':'intruder'}).encode())
        with self.assertRaises(broker.BrokerError):broker.verify_identity('.'.join(parts),'client','nonce',jwks)
if __name__=='__main__':unittest.main(verbosity=2)
