"""Conservative packaging reductions; preserve every Java JAR entry verbatim."""
from pathlib import Path
import hashlib,json,shutil,zipfile

def total(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())
def optimize(resources):
 before=total(resources);removed=[];jars=[]
 python=resources/'python'
 # Standalone Python is statically linked. These files support embedding, Tk UI,
 # installing packages or compiling extensions, none of which Amua invokes.
 relative=['include','lib/pkgconfig','lib/libpython3.12.dylib','lib/libtcl9.0.dylib','lib/libtcl9tk9.0.dylib',
           'lib/tcl9.0','lib/tk9.0','lib/itcl4.3.8','lib/thread3.0.6',
           'lib/python3.12/idlelib','lib/python3.12/tkinter','lib/python3.12/ensurepip',
           'lib/python3.12/site-packages/pip','lib/python3.12/site-packages/setuptools']
 for name in relative:
  p=python/name
  if p.exists():
   n=total(p) if p.is_dir() else p.stat().st_size
   if p.is_dir():shutil.rmtree(p)
   else:p.unlink()
   removed.append({'file':'python/'+name,'bytes':n})
 for p in (python/'bin').iterdir():
  if p.name in ('python','python3','python3.12'):continue
  n=p.stat().st_size if p.exists() and not p.is_symlink() else 0;p.unlink();removed.append({'file':str(p.relative_to(resources)),'bytes':n})
 for source in (resources/'runtime/lib').rglob('*.jar'):
  original=source.stat().st_size;target=source.with_suffix('.repacked')
  with zipfile.ZipFile(source) as incoming,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as out:
   for entry in incoming.infolist():
    data=incoming.read(entry.filename)
    entry.compress_type=zipfile.ZIP_DEFLATED
    out.writestr(entry,data)
  if target.stat().st_size<original:
   with zipfile.ZipFile(source) as old,zipfile.ZipFile(target) as new:
    assert old.namelist()==new.namelist()
    assert all(old.read(n)==new.read(n) for n in old.namelist())
   target.replace(source);jars.append({'file':str(source.relative_to(resources)),'before':original,'after':source.stat().st_size,'all_entry_bytes_equal':True})
  else:target.unlink()
 # CDS caches encode the old rt.jar file layout; the VM can load the intact JAR normally.
 for p in (resources/'runtime').rglob('classes.jsa'):
  removed.append({'file':str(p.relative_to(resources)),'bytes':p.stat().st_size});p.unlink()
 return {'before_bytes':before,'after_bytes':total(resources),'removed':removed,'recompressed_jars':jars}
