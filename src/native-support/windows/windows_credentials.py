"""Windows Credential Manager backend. No subprocess arguments or plaintext fallback."""
import ctypes as C
import hashlib,json,sys,uuid
SERVICE='local.rejie.amua.v21.chatgpt'
MAX_BYTES=65536
CHUNK_BYTES=2048
DWORD=C.c_uint32
BYTE=C.c_ubyte
class FILETIME(C.Structure):_fields_=[('low',DWORD),('high',DWORD)]
class CREDENTIALW(C.Structure):
 _fields_=[('Flags',DWORD),('Type',DWORD),('TargetName',C.c_wchar_p),('Comment',C.c_wchar_p),('LastWritten',FILETIME),('CredentialBlobSize',DWORD),('CredentialBlob',C.POINTER(BYTE)),('Persist',DWORD),('AttributeCount',DWORD),('Attributes',C.c_void_p),('TargetAlias',C.c_wchar_p),('UserName',C.c_wchar_p)]
class CredentialError(RuntimeError):
 def __init__(self):super().__init__('credential_store_unavailable')
class NativeCredentials:
 def __init__(self):
  if sys.platform!='win32':raise CredentialError()
  self.api=C.WinDLL('Advapi32.dll',use_last_error=True);pointer=C.POINTER(CREDENTIALW)
  self.api.CredReadW.argtypes=[C.c_wchar_p,DWORD,DWORD,C.POINTER(pointer)];self.api.CredReadW.restype=C.c_int
  self.api.CredWriteW.argtypes=[pointer,DWORD];self.api.CredWriteW.restype=C.c_int
  self.api.CredDeleteW.argtypes=[C.c_wchar_p,DWORD,DWORD];self.api.CredDeleteW.restype=C.c_int
  self.api.CredEnumerateW.argtypes=[C.c_wchar_p,DWORD,C.POINTER(DWORD),C.POINTER(C.POINTER(pointer))];self.api.CredEnumerateW.restype=C.c_int
  self.api.CredFree.argtypes=[C.c_void_p];self.api.CredFree.restype=None
 def read(self,target):
  value=C.POINTER(CREDENTIALW)()
  if not self.api.CredReadW(target,1,0,C.byref(value)):
   if C.get_last_error()==1168:return None
   raise CredentialError()
  try:
   n=int(value.contents.CredentialBlobSize)
   if not 0<n<=2560:raise CredentialError()
   return C.string_at(value.contents.CredentialBlob,n)
  finally:self.api.CredFree(value)
 def write(self,target,raw):
  if not 0<len(raw)<=2560:raise CredentialError()
  blob=C.create_string_buffer(raw);value=CREDENTIALW();value.Type=1;value.TargetName=target;value.CredentialBlobSize=len(raw);value.CredentialBlob=C.cast(blob,C.POINTER(BYTE));value.Persist=2;value.UserName='Amua ChatGPT'
  if not self.api.CredWriteW(C.byref(value),0):raise CredentialError()
 def delete(self,target):
  if not self.api.CredDeleteW(target,1,0) and C.get_last_error()!=1168:raise CredentialError()
 def targets(self,prefix):
  values=C.POINTER(C.POINTER(CREDENTIALW))();count=DWORD()
  if not self.api.CredEnumerateW(prefix+'*',0,C.byref(count),C.byref(values)):
   if C.get_last_error()==1168:return []
   raise CredentialError()
  try:return [values[i].contents.TargetName for i in range(count.value)]
  finally:self.api.CredFree(values)
class CredentialStore:
 """Chunked generations avoid the native2560-byte blob limit; manifest commits last."""
 def __init__(self,backend=None):self.backend=backend if backend is not None else NativeCredentials()
 def base(self,account):
  if not isinstance(account,str) or not account or len(account)>4096:raise CredentialError()
  return SERVICE+'/'+hashlib.sha256(account.encode()).hexdigest()
 def manifest(self,base):
  raw=self.backend.read(base)
  if raw is None:return None
  try:
   value=json.loads(raw)
   if value.get('schema')!=1 or not isinstance(value.get('generation'),str) or len(value['generation'])!=32 or any(c not in '0123456789abcdef' for c in value['generation']):raise ValueError()
   if type(value.get('chunks'))is not int or not 1<=value['chunks']<=32 or type(value.get('bytes'))is not int or not 1<=value['bytes']<=MAX_BYTES:raise ValueError()
   if not isinstance(value.get('sha256'),str) or len(value['sha256'])!=64:raise ValueError()
   return value
  except Exception:raise CredentialError() from None
 def read(self,account):
  try:
   base=self.base(account);meta=self.manifest(base)
   if meta is None:return None
   parts=[self.backend.read(base+'/'+meta['generation']+'/'+str(i)) for i in range(meta['chunks'])]
   if any(p is None for p in parts):raise CredentialError()
   raw=b''.join(parts)
   if len(raw)!=meta['bytes'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise CredentialError()
   value=json.loads(raw)
   if not isinstance(value,dict):raise CredentialError()
   return value
  except CredentialError:raise
  except Exception:raise CredentialError() from None
 def write(self,account,value):
  try:
   if not isinstance(value,dict):raise CredentialError()
   raw=json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
   if not 0<len(raw)<=MAX_BYTES:raise CredentialError()
   base=self.base(account);old=self.manifest(base);generation=uuid.uuid4().hex;written=[]
   try:
    for i in range(0,len(raw),CHUNK_BYTES):
     target=base+'/'+generation+'/'+str(i//CHUNK_BYTES);self.backend.write(target,raw[i:i+CHUNK_BYTES]);written.append(target)
    meta={'schema':1,'generation':generation,'chunks':len(written),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};self.backend.write(base,json.dumps(meta,separators=(',',':')).encode())
   except Exception:
    for target in written:
     try:self.backend.delete(target)
     except Exception:pass
    raise
   if old:
    for i in range(old['chunks']):
     try:self.backend.delete(base+'/'+old['generation']+'/'+str(i))
     except Exception:pass
  except CredentialError:raise
  except Exception:raise CredentialError() from None
 def delete(self,account):
  try:
   base=self.base(account)
   for target in self.backend.targets(base):
    if target==base or target.startswith(base+'/'):self.backend.delete(target)
  except Exception:raise CredentialError() from None
 def close(self):pass
