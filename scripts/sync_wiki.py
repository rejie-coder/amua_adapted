"""Sync reviewed wiki pages once GitHub's initial Home page has been created."""
from pathlib import Path
import json,os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];REPO='rejie-coder/amua_adapted'
def main():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise SystemExit('Wrong repository')
 with tempfile.TemporaryDirectory(prefix='amua-wiki-') as temporary:
  folder=Path(temporary);ask=folder/'askpass.sh';ask.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "%s\\n" x-access-token ;; *) printf "%s\\n" "$GITHUB_TOKEN" ;; esac\n');ask.chmod(0o700)
  env={**os.environ,'GIT_ASKPASS':str(ask),'GIT_TERMINAL_PROMPT':'0'}
  def git(*args):return subprocess.run(['git',*args],capture_output=True,text=True,env=env)
  wiki=folder/'wiki';clone=git('clone','https://github.com/'+REPO+'.wiki.git',str(wiki))
  if clone.returncode:
   result={'wiki_synced':False,'reason':'Wiki clone unavailable. Create the first Home page in the GitHub Wiki, then rerun Sync wiki. Repository docs are already available.'}
  else:
   for page in (ROOT/'docs/wiki').glob('*.md'):shutil.copy2(page,wiki/page.name)
   for args in [('config','user.name','Amua release automation'),('config','user.email','github-actions[bot]@users.noreply.github.com'),('add','--','*.md')]:
    if git('-C',str(wiki),*args).returncode:raise RuntimeError('Wiki staging failed')
   changed=git('-C',str(wiki),'diff','--cached','--quiet').returncode
   if changed:
    if git('-C',str(wiki),'commit','-m','Document Amua 3.3.3 Intel preview').returncode or git('-C',str(wiki),'push','origin','HEAD').returncode:raise RuntimeError('Wiki publication failed; inspect repository permissions')
   result={'wiki_synced':True,'url':'https://github.com/'+REPO+'/wiki','pages':len(list((ROOT/'docs/wiki').glob('*.md')))}
 (ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence/wiki-sync.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
