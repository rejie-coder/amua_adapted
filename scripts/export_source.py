"""Export application sources and docs without runtimes, private inputs or Git state."""
from pathlib import Path
import tarfile
ROOT=Path(__file__).resolve().parents[1]
def export():
 target=ROOT/'dist/Amua-3.2.4-source.tar.gz';target.parent.mkdir(exist_ok=True)
 with tarfile.open(target,'w:gz') as tar:
  for item in sorted(ROOT.iterdir()):
   if item.name in {'.git','build','dist','Amua.app','evidence','__pycache__'}:continue
   tar.add(item,arcname='amua_adapted-3.2.4/'+item.name,filter=lambda i:None if any(p in {'.DS_Store','__pycache__','.git'} for p in Path(i.name).parts) else i)
 with tarfile.open(target) as tar:
  names=tar.getnames()
  if any('/evidence/inputs/' in n or '/evidence/prior/' in n or '/.git/' in n or '/build/' in n or '/Amua.app/' in n for n in names):raise RuntimeError('Private/build state entered source archive')
 print('Exported source archive:',target);return target
if __name__=='__main__':export()
