"""Publish checked Apple Silicon assets as a GitHub preview. GITHUB_TOKEN stays in memory."""
from pathlib import Path
import hashlib,json,os,urllib.error,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[1];REPO='rejie-coder/amua_adapted'
def main():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise SystemExit('Wrong repository; refusing publication')
 token=os.environ['GITHUB_TOKEN'];commit=os.environ['GITHUB_SHA'];base='https://api.github.com/repos/'+REPO
 def request(method,url,data=None,binary=False):
  body=data if binary else None if data is None else json.dumps(data).encode()
  headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'Amua-release/3.3.3','X-GitHub-Api-Version':'2022-11-28'}
  if body is not None:headers['Content-Type']='application/octet-stream' if binary else 'application/json'
  with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=headers,method=method),timeout=180) as response:return json.load(response)
 report=json.loads((ROOT/'evidence/release-verification.json').read_text());assert report['application_classes_match_local_candidate']==718
 try:release=request('GET',base+'/releases/tags/v3.3.3-arm64')
 except urllib.error.HTTPError as error:
  if error.code!=404:raise
  release=None
 if release is not None and (not release['draft'] or release['target_commitish']!=commit):raise SystemExit('An existing release belongs to another commit or is already public; refusing to replace it')
 if release is None:release=request('POST',base+'/releases',{'tag_name':'v3.3.3-arm64','target_commitish':commit,'name':'Amua 3.3.3 for Apple Silicon — preview','body':(ROOT/'docs/Release-Notes-3.3.3-arm64.md').read_text(),'draft':True,'prerelease':True})
 existing={a['name']:a for a in release.get('assets',[])}
 for path in sorted((ROOT/'dist').iterdir()):
  if not path.is_file():continue
  if path.name in existing:raise SystemExit('Draft asset already exists; inspect before retrying: '+path.name)
  request('POST',release['upload_url'].split('{',1)[0]+'?name='+urllib.parse.quote(path.name),path.read_bytes(),True)
 # Verify uploaded checksums, then read the DMG and ZIP back before publication.
 expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'dist').iterdir() if p.is_file()}
 current=request('GET',base+'/releases/'+str(release['id']))
 if {a['name'] for a in current['assets']} != set(expected):raise RuntimeError('Uploaded release asset set differs from dist')
 for asset in current['assets']:
  if asset['name'] not in expected or asset.get('digest')!='sha256:'+expected[asset['name']]:raise RuntimeError('Uploaded asset digest mismatch: '+asset['name'])
 readbacks={}
 for asset in current['assets']:
  if not asset['name'].endswith(('.dmg','.zip')):continue
  headers={'Authorization':'Bearer '+token,'Accept':'application/octet-stream','User-Agent':'Amua-release/3.3.3'}
  h=hashlib.sha256()
  with urllib.request.urlopen(urllib.request.Request(asset['url'],headers=headers),timeout=300) as stream:
   if 'application/json' in stream.headers.get('Content-Type',''):raise RuntimeError('Asset readback did not return binary bytes')
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
  if h.hexdigest()!=expected[asset['name']]:raise RuntimeError('Uploaded readback differs: '+asset['name'])
  readbacks[asset['name']]=h.hexdigest()
 final=request('PATCH' ,base+'/releases/'+str(release['id']),{'draft':False,'prerelease':True})
 result={'url':final['html_url'],'tag':final['tag_name'],'commit':commit,'prerelease':final['prerelease'],'uploaded_readbacks':readbacks,'assets':[{'name':a['name'],'bytes':a['size'],'url':a['browser_download_url'],'digest':a.get('digest')} for a in final['assets']]}
 (ROOT/'evidence/published-release.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
