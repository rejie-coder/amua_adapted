"""Publish verified Windows assets; preserve existing releases and their tags."""
from pathlib import Path
import hashlib,json,os,urllib.error,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[1];REPO='rejie-coder/amua_adapted';TAG='v3.3.1-windows'
def main():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/windows-3.3.1':raise SystemExit('Wrong repository or branch')
 checks=json.loads((ROOT/'evidence/windows-checks.json').read_text())
 from package_windows import require_checks
 require_checks(checks)
 commit=os.environ['GITHUB_SHA'];token=os.environ['GITHUB_TOKEN'];base='https://api.github.com/repos/'+REPO
 def request(method,url,data=None,binary=False):
  body=data if binary else None if data is None else json.dumps(data).encode()
  headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'Amua-Windows-release/3.3.1','X-GitHub-Api-Version':'2022-11-28'}
  if body is not None:headers['Content-Type']='application/octet-stream' if binary else 'application/json'
  with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=headers,method=method),timeout=300) as response:return json.load(response)
 try:release=request('GET',base+'/releases/tags/'+TAG)
 except urllib.error.HTTPError as error:
  if error.code!=404:raise
  release=None
 if release is not None:raise SystemExit('Windows release already exists; inspect it before retrying. No assets replaced.')
 files=sorted((ROOT/'dist').iterdir());expected={'Amua-3.3.1-Windows-x64.zip','Amua-3.3.1-Windows-source.tar.gz','README-WINDOWS.txt','windows-checks.json','package-verification.json','build-provenance.json','TEST_REPORT.md','RED_TEAM.md','SHA256SUMS'}
 if {p.name for p in files}!=expected or not all(p.is_file() for p in files):raise SystemExit('Unexpected release assets')
 sums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 recorded=dict((line.split('  ',1)[1],line.split('  ',1)[0]) for line in (ROOT/'dist/SHA256SUMS').read_text().splitlines())
 if recorded!={k:v for k,v in sums.items() if k!='SHA256SUMS'}:raise SystemExit('Release checksum manifest differs')
 request('POST',base+'/git/refs',{'ref':'refs/tags/'+TAG,'sha':commit})
 release=request('POST',base+'/releases',{'tag_name':TAG,'target_commitish':commit,'name':'Amua 3.3.1 for Windows x64 — preview','body':(ROOT/'docs/Release-Notes-3.3.1-Windows.md').read_text(),'draft':True,'prerelease':True})
 uploaded=[]
 for path in files:
  asset=request('POST',release['upload_url'].split('{',1)[0]+'?name='+urllib.parse.quote(path.name),path.read_bytes(),True)
  if asset['size']!=path.stat().st_size or asset.get('digest')!='sha256:'+sums[path.name]:raise RuntimeError('Uploaded asset digest/size mismatch: '+path.name)
  uploaded.append(asset)
 # Read the entire uploaded portable ZIP back before making the release public.
 zip_asset=next(a for a in uploaded if a['name'].endswith('-x64.zip'))
 headers={'Authorization':'Bearer '+token,'Accept':'application/octet-stream','User-Agent':'Amua-Windows-release/3.3.1'}
 digest=hashlib.sha256()
 with urllib.request.urlopen(urllib.request.Request(zip_asset['url'],headers=headers),timeout=300) as response:
  if 'application/json' in response.headers.get('Content-Type',''):raise RuntimeError('Asset endpoint did not return ZIP bytes')
  for block in iter(lambda:response.read(1024*1024),b''):digest.update(block)
 if digest.hexdigest()!=sums[zip_asset['name']]:raise RuntimeError('Published ZIP readback mismatch')
 tag=request('GET',base+'/git/ref/tags/'+TAG)
 if tag['object']['sha']!=commit:raise RuntimeError('Release tag differs from tested commit')
 final=request('PATCH',base+'/releases/'+str(release['id']),{'draft':False,'prerelease':True})
 result={'url':final['html_url'],'tag':TAG,'commit':commit,'published_zip_readback_sha256':digest.hexdigest(),'assets':[{'name':a['name'],'bytes':a['size'],'digest':a.get('digest'),'url':a['browser_download_url']} for a in final['assets']]}
 (ROOT/'evidence/published-windows.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
