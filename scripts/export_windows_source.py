"""Export only public build inputs, including synthetic engine fixtures."""
from pathlib import Path
import tarfile
ROOT=Path(__file__).resolve().parents[1]
def export():
 target=ROOT/'dist/Amua-3.3.2-Windows-source.tar.gz';target.parent.mkdir(exist_ok=True)
 entries=['src','scripts','tests','docs','.github','.gitattributes','.gitignore','LICENSE','NOTICE.md','README.md','README-WINDOWS.txt','RED_TEAM.md','TEST_REPORT.md','CONTRIBUTING.md','SECURITY.md','evidence/engine-parity']
 with tarfile.open(target,'w:gz') as archive:
  for name in entries:
   archive.add(ROOT/name,arcname='amua_adapted-3.3.2-windows/'+name,filter=lambda item:None if any(p in {'.DS_Store','__pycache__','.git'} for p in Path(item.name).parts) else item)
 with tarfile.open(target) as archive:
  names=archive.getnames()
  for name in names:
   relative=Path(name).parts[1:]
   if any(p in {'build','dist','Amua','Amua.app','.git','__pycache__'} for p in relative):raise RuntimeError('Generated state entered source archive')
   if 'evidence' in relative and relative[:2]!=('evidence','engine-parity'):raise RuntimeError('Non-public evidence entered source archive')
 print('Public Windows source archive verified:',target);return target
if __name__=='__main__':export()
