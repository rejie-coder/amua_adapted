"""No-network source intake, draft ledger and atomic local project persistence.

Source formulas are preserved and conservatively traced, never evaluated. This
module does not provide an Excel calculation engine or clinical interpretation.
"""
import csv
import copy
import hashlib
import io
import json
import os
import posixpath
import re
import stat
import struct
import tempfile
import time
import uuid
import zipfile
try:
    import fcntl
except ImportError:
    import windows_locking as fcntl
from collections import Counter, defaultdict, deque
from decimal import Decimal
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
MAX_FILE = 25*1024*1024
MAX_TOTAL = 100*1024*1024
MAX_EXPANDED = 250*1024*1024
MAX_CELLS = 100000
MAX_PROJECT_BYTES = 12*1024*1024
SCHEMA = 1

class WorkflowError(ValueError): pass

def uid(): return str(uuid.uuid4())
def digest(data): return hashlib.sha256(data).hexdigest()
def encoded(obj): return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',',':')).encode('utf-8')
def sid(source, locator): return str(uuid.uuid5(uuid.NAMESPACE_URL, source+':'+locator))

class BoundedXML(ET.TreeBuilder):
    def __init__(self):super().__init__();self.depth=0;self.nodes=0;self.text_size=0
    def doctype(self,*args):raise WorkflowError('XML entities and DTDs are unsupported')
    def start(self,tag,attrs):
        self.depth+=1;self.nodes+=1;self.text_size=0
        if self.depth>101 or self.nodes>250000:raise WorkflowError('XML depth or element limit exceeded')
        if sum(len(k)+len(v) for k,v in attrs.items())>1000000:raise WorkflowError('XML attribute limit exceeded')
        return super().start(tag,attrs)
    def end(self,tag):self.depth-=1;self.text_size=0;return super().end(tag)
    def data(self,text):
        self.text_size+=len(text)
        if self.text_size>1000000:raise WorkflowError('XML string limit exceeded')
        return super().data(text)

def xml(data):
    if len(data)>32*1024*1024:raise WorkflowError('XML input limit exceeded')
    return ET.fromstring(data,parser=ET.XMLParser(target=BoundedXML()))

def read_project_bytes(path):
    with os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_PROJECT_BYTES:raise WorkflowError('Project archive exceeds the 12 MiB supported limit')
        data=stream.read(MAX_PROJECT_BYTES+1)
        if len(data)>MAX_PROJECT_BYTES:raise WorkflowError('Project archive exceeds the 12 MiB supported limit')
        return data

def project_budget(project):
    if len(encoded(project))>MAX_PROJECT_BYTES:raise WorkflowError('Combined project inventory exceeds 12 MiB; keep this source in a separate project')
    return project

def archive(data):
    z=zipfile.ZipFile(io.BytesIO(data))
    infos=z.infolist()
    names=[i.filename for i in infos]
    if len(infos)>20000 or len(set(names))!=len(names): raise WorkflowError('Duplicate or excessive ZIP entries')
    total=0
    for item in infos:
        path=PurePosixPath(item.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in item.filename: raise WorkflowError('Unsafe ZIP path')
        if stat.S_ISLNK(item.external_attr>>16): raise WorkflowError('ZIP symlinks are unsupported')
        total+=item.file_size
        if total>MAX_EXPANDED or item.file_size>MAX_EXPANDED: raise WorkflowError('Expanded ZIP limit exceeded')
        if item.file_size>max(1024*1024,item.compress_size*1000): raise WorkflowError('ZIP compression ratio limit exceeded')
    return z

def column_number(text):
    out=0
    for c in text: out=out*26+ord(c)-64
    return out

def column_name(number):
    result=''
    while number:
        number,r=divmod(number-1,26); result=chr(65+r)+result
    return result

CELL = re.compile(r'(?<![A-Za-z0-9_])(?P<cabs>\$?)(?P<c>[A-Z]{1,3})(?P<rabs>\$?)(?P<r>[1-9][0-9]*)(?![A-Za-z0-9_])')
def translate_formula(formula, origin, target):
    a=CELL.fullmatch(origin); b=CELL.fullmatch(target)
    dc=column_number(b['c'])-column_number(a['c']); dr=int(b['r'])-int(a['r'])
    def replace(m):
        c=column_number(m['c'])+(0 if m['cabs'] else dc)
        r=int(m['r'])+(0 if m['rabs'] else dr)
        if not 1<=c<=16384 or not 1<=r<=1048576: return '#REF!'
        return m['cabs']+column_name(c)+m['rabs']+str(r)
    # Excel string literals are not references. Quoted worksheet names are kept.
    parts=re.split(r'''("(?:[^"]|"")*"|'(?:[^']|'')*')''',formula)
    return ''.join(part if i%2 else CELL.sub(replace,part) for i,part in enumerate(parts))

def relationships(z, path):
    if path not in z.namelist(): return []
    root=xml(z.read(path))
    return [dict(n.attrib) for n in root]

def workbook(data, source_id):
    with archive(data) as z:
        wb=xml(z.read('xl/workbook.xml'))
        rels=relationships(z,'xl/_rels/workbook.xml.rels')
        targets={r['Id']:r.get('Target','') for r in rels}
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(n.itertext()) for n in xml(z.read('xl/sharedStrings.xml'))]
        sheets=[]; count=0
        for sheet in wb.find('s:sheets',NS):
            target=targets[sheet.attrib[RID]]
            path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not path.startswith('xl/'): raise WorkflowError('Worksheet relationship escapes workbook')
            root=xml(z.read(path)); name=sheet.get('name')
            records=[]; masters={}
            for c in root.findall('.//s:sheetData/s:row/s:c',NS):
                count+=1
                if count>MAX_CELLS: raise WorkflowError('Physical cell record limit exceeded')
                f=c.find('s:f',NS); v=c.find('s:v',NS); inline=c.find('s:is',NS)
                value=v.text if v is not None else None
                if c.get('t')=='s' and value is not None:
                    try: value=strings[int(value)]
                    except (IndexError,ValueError): raise WorkflowError('Invalid shared string index')
                if inline is not None: value=''.join(inline.itertext())
                rec={'id':sid(source_id,name+'!'+c.get('r','')), 'cell':c.get('r'), 'attributes':dict(c.attrib),
                     'cached_value':value,'value_kind':'source-error' if c.get('t')=='e' else ('cached' if f is not None else 'literal'),
                     'has_value_formula_inline': any(x is not None for x in (f,v,inline)),
                     'formula':None if f is None else (f.text or ''), 'formula_attributes':{} if f is None else dict(f.attrib)}
                if f is not None and f.get('t')=='shared' and f.text: masters[f.get('si')]=(c.get('r'),f.text)
                records.append(rec)
            for rec in records:
                rec['effective_formula']=rec['formula']
                if rec['formula_attributes'].get('t')=='shared' and not rec['formula']:
                    master=masters.get(rec['formula_attributes'].get('si'))
                    rec['effective_formula']=translate_formula(master[1],master[0],rec['cell']) if master else None
                    if not master: rec['formula_issue']='Missing shared formula master'
            notes=[]
            for element in root:
                if element.tag.rsplit('}',1)[-1] not in ('sheetData',):
                    notes.append({'tag':element.tag.rsplit('}',1)[-1],'xml':ET.tostring(element,encoding='unicode')})
            rp=posixpath.dirname(path)+'/_rels/'+posixpath.basename(path)+'.rels'
            sheets.append({'id':sid(source_id,'sheet:'+name),'name':name,'state':sheet.get('state','visible'),
                           'part':path,'cells':records,'properties':notes,'relationships':relationships(z,rp)})
        parts=[{'id':sid(source_id,'part:'+i.filename),'name':i.filename,'bytes':i.file_size,'sha256':digest(z.read(i)), **({'extracted_xml':ET.tostring(xml(z.read(i)),encoding='unicode')} if i.filename.endswith(('.xml','.rels')) and any(t in i.filename for t in ('drawings/','comments','tables/','externalLinks/')) else {})}
               for i in z.infolist() if not i.is_dir()]
        unsupported=[]
        for p in parts:
            name=p['name']
            if any(s in name for s in ('externalLinks/','vbaProject','pivot','queryTables/')): unsupported.append(name)
        result={'sheets':sheets,'parts':parts,'relationships':rels,'defined_names':[
            dict(n.attrib,text=n.text) for n in wb.findall('.//s:definedName',NS)],
            'drawing_parts':[p for p in parts if p['name'].startswith('xl/drawings/')],
            'media_parts':[p for p in parts if p['name'].startswith('xl/media/')],
            'unsupported_constructs':unsupported,'recalculation':'not performed; cached values only'}
        result['dependencies']=dependencies(sheets)
        return result

REF=re.compile(r"(?:(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_ .]*))!)?(\$?[A-Z]{1,3}\$?[1-9][0-9]*)(?::(\$?[A-Z]{1,3}\$?[1-9][0-9]*))?")
def dependencies(sheets):
    index={(s['name'],c['cell']):c for s in sheets for c in s['cells']}
    reverse=defaultdict(set); edges=set(); roots=[]; unsupported=[];operations=0
    for (name,address),cell in index.items():
        formula=cell['effective_formula']
        if cell['value_kind']=='source-error' or (formula and '#REF!' in formula): roots.append(cell['id'])
        if not formula: continue
        if '[' in formula or 'INDIRECT(' in formula.upper() or 'OFFSET(' in formula.upper(): unsupported.append(cell['id'])
        # Conservative lexical references; functions, named formulas, dynamic ranges
        # remain unsupported, and are never marked completely evaluated.
        for match in REF.finditer(re.sub(r'"(?:[^"]|"")*"','',formula)):
            sheet=(match[1] or match[2] or name).replace("''", "'")
            start=match[3].replace('$',''); end=(match[4] or start).replace('$','')
            a=CELL.fullmatch(start); b=CELL.fullmatch(end)
            width=column_number(b['c'])-column_number(a['c'])+1; height=int(b['r'])-int(a['r'])+1
            if width<1 or height<1 or width*height>MAX_CELLS: unsupported.append(cell['id']);continue
            operations+=width*height
            if operations>2000000:raise WorkflowError('Formula dependency operation limit exceeded; source scope remains incomplete')
            for col in range(column_number(a['c']),column_number(b['c'])+1):
                for row in range(int(a['r']),int(b['r'])+1):
                    dep=index.get((sheet,column_name(col)+str(row)))
                    if dep:
                        reverse[dep['id']].add(cell['id']); edges.add((dep['id'],cell['id']))
    seen=set(roots); queue=deque(roots)
    while queue:
        for nxt in reverse[queue.popleft()]:
            if nxt not in seen:seen.add(nxt);queue.append(nxt)
    # Kahn remainder detects cyclic or cycle-dependent formulas conservatively.
    indegree=Counter(b for a,b in edges); todo=deque(k for k in {c['id'] for c in index.values()} if not indegree[k]); removed=set()
    while todo:
        cur=todo.popleft();removed.add(cur)
        for nxt in reverse[cur]:
            indegree[nxt]-=1
            if indegree[nxt]==0:todo.append(nxt)
    return {'edges':[list(edge) for edge in sorted(edges)],'error_roots':sorted(set(roots)),'affected_error_closure':sorted(seen),
            'cycle_or_dependent':sorted(k for k,v in indegree.items() if v>0),
            'unsupported_dynamic_or_external':sorted(set(unsupported)),
            'scope':'conservative A1 lexical dependencies; named/dynamic/structured formula semantics not evaluated'}

def image_size(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>=24:return struct.unpack('>II',data[16:24])
    if data.startswith(b'\xff\xd8'):
        pos=2
        while pos+4<=len(data):
            if data[pos]!=255:pos+=1;continue
            marker=data[pos+1];pos+=2
            if marker in (0xd8,0xd9):continue
            length=int.from_bytes(data[pos:pos+2],'big')
            if length<2:break
            if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                if pos+7>len(data):break
                return int.from_bytes(data[pos+5:pos+7],'big'),int.from_bytes(data[pos+3:pos+5],'big')
            pos+=length
    raise WorkflowError('Unsupported or malformed image header')

def intake(paths, options=None):
    options=options or {}
    max_file=int(options.get("max_file_bytes",MAX_FILE));max_total=int(options.get("max_total_bytes",MAX_TOTAL))
    if not 1<=max_file<=100*1024*1024 or not 1<=max_total<=500*1024*1024:raise WorkflowError("Unsupported source byte limits")
    selected=[];exclusions=[]
    for input_path in paths:
        path=Path(input_path).absolute()
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise WorkflowError('Symlink selections are unsupported; select a resolved ordinary path')
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.name.startswith('.') or child.is_symlink() or not child.is_file():exclusions.append({'name':child.name,'reason':'hidden, symlink, nested directory or special file'})
                else:selected.append(child)
        else:selected.append(path)
    if not selected or len(selected)>20:raise WorkflowError('Select between 1 and 20 ordinary files')
    files=[];total=0;expanded_total=0;cell_total=0
    for number,path in enumerate(selected):
        with os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size>max_file:raise WorkflowError('Invalid file or file size limit exceeded')
            data=stream.read(max_file+1);after=os.fstat(stream.fileno())
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise WorkflowError('Source changed during selection')
        total+=len(data)
        if len(data)>max_file or total>max_total:raise WorkflowError('Selected size limit exceeded')
        sha=digest(data);source_index=int(options.get('selection_offset',0))+number;source_id=sid(sha,str(options.get('selection_identity',source_index)))
        source={'id':source_id,'name':path.name,'selection_index':source_index,'sha256':sha,'bytes':len(data)}
        suffix=path.suffix.lower()
        if suffix=='.xlsx':source.update(workbook(data,source_id));source['kind']='workbook'
        elif suffix in ('.png','.jpg','.jpeg'):
            w,h=image_size(data)
            if w*h>40000000:raise WorkflowError('Image pixel limit exceeded')
            source.update(kind='image',width=w,height=h,regions=[{'id':sid(source_id,'whole-image'),'bounds':[0,0,w,h],'status':'unresolved','reason':'visual ancestry requires review'}])
        elif suffix in ('.docx','.pdf','.html','.htm'):
            from .mixed_formats import docx,pdf,html_article
            try:source.update({'.docx':docx,'.pdf':pdf,'.html':html_article,'.htm':html_article}[suffix](data,source_id))
            except Exception as exc:
                source.update(kind='parse-error',document_format=suffix[1:].upper(),reason=str(exc) if isinstance(exc,WorkflowError) else 'Document could not be parsed; no source scope is considered complete',error_category=type(exc).__name__,extraction_status='incomplete')
        elif suffix in ('.txt','.csv','.md','.rst','.tsv','.json'):
            text=data.decode('utf-8-sig');source['kind']='text'
            source['records']=[{'id':sid(source_id,str(i)),'line':i,'text':line} for i,line in enumerate(text.splitlines(),1)]
            if suffix=='.csv':source['csv_rows']=list(csv.reader(io.StringIO(text)))
        else:source.update(kind='unsupported',reason='Unsupported selected format; retained in ledger')
        expanded_total+=sum(part['bytes'] for part in source.get('parts',[]))
        cell_total+=sum(len(sheet['cells']) for sheet in source.get('sheets',[]))
        if expanded_total>MAX_EXPANDED or cell_total>MAX_CELLS:raise WorkflowError('Combined workbook expansion or physical record limit exceeded')
        files.append(source)
    project={'schema':SCHEMA,'project_id':uid(),'generation_id':uid(),'revision':0,'geometry_revision':0,'session_id':uid(),
             'state':'draft_incomplete','source_set_hash':digest(encoded([(f['id'],f['sha256']) for f in files])),
             'graph':{'nodes':[]},'unknowns':[],'parameters':{},'modules':{},'layout':{},
             'provenance':{'files':files,'coverage':[],'assumptions':[],'review':{'domain':'not reviewed'},'exclusions':exclusions},'results':[]}
    root=uid();project['graph']['nodes'].append({'id':root,'label':'Selected source draft','parent':None,'relationship':'presentation','terminal':False,'source_ids':[]})
    for f in files:
        for item in source_items(f):project['provenance']['coverage'].append({'source_id':item,'status':'unresolved','reason':'Inventoried; semantic interpretation pending'})
        parent=uid();project['graph']['nodes'].append({'id':parent,'label':f['name'],'parent':root,'relationship':'presentation','terminal':False,'source_ids':[f['id']]})
        for sheet in f.get('sheets',[]):
            project['graph']['nodes'].append({'id':uid(),'label':sheet['name'],'parent':parent,'relationship':'presentation','terminal':True,'source_ids':[sheet['id']]})
        if f['kind']=='workbook':
            errors=sum(c['value_kind']=='source-error' for s in f['sheets'] for c in s['cells'])
            if errors:project['unknowns'].append(question('Correct broken references and cached errors before affected calculations.', 'mapping','cell references',[parent],f['id']))
            project['unknowns'].append(question('Confirm authoritative costs, horizon, perspective and intended outcomes.','mapping','declared basis',[parent],f['id']))
    project['unknowns'].append(question('Review all selected source records and classify their intended scope.','mapping','coverage',[root],project['source_set_hash']))
    return project

def source_items(source):
    yield source['id']
    for sheet in source.get('sheets',[]):
        yield sheet['id']
        for cell in sheet['cells']:yield cell['id']
    for part in source.get('parts',[]):yield part['id']
    for record in source.get('records',[]):yield record['id']
    for region in source.get('regions',[]):yield region['id']
    for page in source.get('pages',[]):yield page['id']
    for rel in source.get('relationships',[]):
        if 'id' in rel:yield rel['id']

def refresh_pdf_batch(project,path,start,count):
    from .mixed_formats import pdf
    project=copy.deepcopy(project);p=Path(path)
    if p.is_symlink() or any(parent.is_symlink() for parent in p.parents):raise WorkflowError('Select an ordinary PDF path')
    with os.fdopen(os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise WorkflowError('Select an ordinary PDF file')
        data=stream.read(MAX_FILE+1)
    if len(data)>MAX_FILE:raise WorkflowError('PDF input limit exceeded')
    source=next((f for f in project['provenance']['files'] if f['name']==p.name and f['sha256']==digest(data)),None)
    if source is None:raise WorkflowError('PDF changed or is not in the inspected source set; inspect again')
    incoming=pdf(data,source['id'],ocr_start=start,ocr_count=count)
    selected=set(range(start,start+count))
    oldids=set(source_items(source))
    source['records']=[r for r in source.get('records',[]) if r.get('page') not in selected]+[r for r in incoming['records'] if r.get('page') in selected]
    source['pages']=[next((n for n in incoming['pages'] if n['page']==page['page']),page) if page['page'] in selected else page for page in source['pages']]
    selected_ids={p['id'] for p in incoming['pages'] if p['page'] in selected}
    source['parse_issues']=[i for i in source.get('parse_issues',[]) if i.get('page_id') not in selected_ids]+[i for i in incoming.get('parse_issues',[]) if i.get('page_id') in selected_ids]
    coverage={c['source_id']:c for c in project['provenance']['coverage']}
    newids=set(source_items(source))
    for identity in oldids-newids:coverage.pop(identity,None)
    for identity in newids:coverage.setdefault(identity,{'source_id':identity,'status':'unresolved','reason':'OCR source batch remains scientifically unreviewed'})
    project['provenance']['coverage']=list(coverage.values());project['revision']+=1
    return project_budget(project)

def question(text,kind,unit,affected,source):
    return {'id':uid(),'question':text,'type':kind,'unit':unit,'affected':affected,'source_ids':[source],'status':'unresolved','answer':None}

def d2p_draft(project):
    files=project['provenance']['files']
    by_name={f['name']:f for f in files}
    required=['D2P cost analysis Cluster care.xlsx','d2p_tree_v2.png','d2p_tree.png']
    if any(n not in by_name for n in required):raise WorkflowError('Select the D2P workbook and both reference PNGs for the full D2P draft')
    expected_images={'d2p_tree_v2.png':'67fe64e9614bac88f024dd57d9824b16ea136217487dd7d5c6f9b8987f766683','d2p_tree.png':'0fab55b3a84594bd8ae28829ad961df29fdbd049fb41997735ae6ccf1cc62332'}
    if any(by_name[name]['sha256']!=sha for name,sha in expected_images.items()):raise WorkflowError('Reference images changed; prior engineering transcription cannot be reused without visual review')
    nodes=[]
    references=[by_name[n]['id'] for n in required]
    def add(label,parent=None,module=None,terminal=False,relationship='presentation',**extra):
        node={'id':uid(),'label':label,'parent':parent,'module':module,'terminal':terminal,'relationship':relationship,'source_ids':references}
        node.update(extra);nodes.append(node);return node['id']
    root=add('Diabetes care strategy');add('Status quo — comparator unresolved',root,terminal=True,relationship='alternative')
    programme=add('D2P cluster care',root,relationship='alternative')
    a=add('A Facility readiness',programme,'A',relationship='additive-module')
    add('DGH + Type A',a,'A',True);add('Type B',a,'A',True)
    def binary(parent,levels,module):
        if not levels:return
        for label in levels[0]:
            child=add(label,parent,module,len(levels)==1,relationship='conditional-presentation',allocation='unresolved; marginal data are not joint probabilities')
            binary(child,levels[1:],module)
    for label in ('Divisional hospitals','PMCUs'):
        group=add(label,a,'A');binary(group,[['Lacks ECG','Has ECG'],['Lacks ophthalmoscope','Has ophthalmoscope'],['Lacks tuning fork','Has tuning fork']],'A')
    b=add('B Digital readiness',programme,'B',relationship='additive-module')
    hospitals=add('Hospitals (DGH, BH, DH)',b,'B')
    binary(hospitals,[['Lacks laptops & readers','Has laptops & readers'],['Lacks network','Has network']],'B')
    pmcu=add('PMCUs',b,'B');binary(pmcu,[['Lacks network','Has network']],'B')
    c=add('C Patient care',programme,'C',relationship='additive-module')
    for label,creatinine in [('Diagnosed diabetic nephropathy',4),('Undiagnosed diabetic nephropathy [source label; meaning unresolved]',1)]:
        add(label,c,'C',True,components=[{'label':'HbA1c','frequency_per_year':4},{'label':'Microalbumin','frequency_per_year':1},
            {'label':'S. creatinine','frequency_per_year':creatinine},{'label':'Lipid profile','frequency_per_year':1},{'label':'Pre-pack consumables','frequency_per_year':None}],
            classification='source wording; not clinically validated')
    ledger=[]
    for label,period in [('Referral & back-referral','one-off'),('Pre-packing machines','one-off'),('Training module, ToT, roll-out and pen drives','one-off'),('Monofilaments','one-off'),('Sticker rolls','one-off'),('PHN cards','one-off'),('ECG rolls','year-1 and annual'),('Local training','annual'),('Network maintenance','three-year'),('Connectivity and data-centre fees','source FOC/exclusion; confirm')]:
        ledger.append({'id':uid(),'label':label,'period':period,'allocation':'once per declared programme period','status':'unresolved','source_ids':references})
    project['graph']={'nodes':nodes,'programme_ledger':ledger,'reference_status':'Engineering transcription of supplied images; scientific claims unreviewed'}
    project['unknowns']=[question(text,kind,unit,affected,by_name[required[0]]['id']) for text,kind,unit,affected in [
        ('Resolve 1,127 tier total versus 1,159 denominator; specify population per module.','mapping','facilities',[a,b]),
        ('Provide joint equipment gaps or explicitly review a conditional allocation assumption.','mapping','joint distribution',[a]),
        ('Confirm whether laptop and reader shortages refer to the same facilities.','mapping','facilities',[b]),
        ('Clarify source label “undiagnosed diabetic nephropathy”; prevalence complement does not establish it.','text','classification',[c]),
        ('Provide status-quo costs and health outcomes before incremental or cost-effectiveness analysis.','mapping','LKR and outcomes',[root]),
        ('Confirm first-year/recurrent horizon, currency base year, perspective, three-year maintenance, annualization and exclusions.','mapping','basis',[programme]),
        ('Complete semantic coverage and numerical reconciliation for every inventoried source item.','mapping','coverage',[programme])]]
    project['revision']+=1;project['state']='draft_incomplete'
    return project

def validate_graph(project):
    nodes=project['graph']['nodes'];ids=[n['id'] for n in nodes]
    if len(nodes)>10000 or len(set(ids))!=len(ids):raise WorkflowError('Duplicate node identity or graph limit exceeded')
    parents={n['id']:n['parent'] for n in nodes}
    if nodes and sum(p is None for p in parents.values())!=1:raise WorkflowError('Graph requires exactly one root')
    for node,parent in parents.items():
        seen=set();cur=node
        while cur is not None:
            if cur not in parents:raise WorkflowError('Unknown parent')
            if cur in seen or len(seen)>100:raise WorkflowError('Graph cycle or depth limit exceeded')
            seen.add(cur);cur=parents[cur]
    sources={x for f in project['provenance']['files'] for x in source_items(f)}
    for node in nodes:
        if any(s not in sources for s in node.get('source_ids',[])):raise WorkflowError('Unknown citation')
    coverage=project['provenance']['coverage']
    if Counter(c['source_id'] for c in coverage)!=Counter(sources):raise WorkflowError('Source coverage identity mismatch')
    return True

def answer_question(project, question_id, value, unit, expected_revision):
    if expected_revision!=project['revision']:raise WorkflowError('Stale question sheet or project revision')
    q=next((q for q in project['unknowns'] if q['id']==question_id),None)
    if q is None:raise WorkflowError('Unknown question')
    if unit!=q['unit']:raise WorkflowError('Answer unit mismatch')
    if q['type']=='number':
        try:number=Decimal(str(value))
        except Exception:raise WorkflowError('Expected finite number')
        if not number.is_finite():raise WorkflowError('Expected finite number')
    elif q['type']=='mapping' and not isinstance(value,dict):raise WorkflowError('Expected structured mapping; free text is not a resolved mapping')
    elif q['type']=='text' and (not isinstance(value,str) or not value.strip()):raise WorkflowError('Expected nonempty text')
    q.update(status='answered_pending_review',answer=value,answered_at=time.time(),basis='user-supplied; interpretation requires review')
    project['revision']+=1;project['state']='draft_incomplete'
    for result in project['results']:
        if set(result.get('dependencies',[])) & set(q['affected']):result['stale']=True
    return project

def summary(project):
    files=project['provenance']['files'];sheets=[s for f in files for s in f.get('sheets',[])]
    return {'files':len(files),'sheets':len(sheets),'cell_records':sum(len(s['cells']) for s in sheets),
            'cached_errors':sum(c['value_kind']=='source-error' for s in sheets for c in s['cells']),
            'pages':sum(len(f.get('pages',[])) for f in files),'document_sources':sum(f['kind'] in ('document','pdf','article') for f in files),'unreadable_or_failed_regions':sum(len(f.get('parse_issues',[])) for f in files),'unsupported_or_failed_sources':sum(f['kind'] in ('unsupported','parse-error') for f in files),'nodes':len(project['graph']['nodes']),'unresolved_questions':sum(q['status']!='resolved' for q in project['unknowns']),
            'state':project['state'],'can_export_legacy':False,'message':'Draft only. Source formulas have not been recalculated; affected calculations and legacy export remain blocked.'}

def components(project):
    validate_graph(project)
    return {'graph.json':{'graph':project['graph'],'unknowns':project['unknowns']},'parameters.json':project['parameters'],
            'provenance.json':project['provenance'],'layout.json':project['layout'],'project.json':{k:v for k,v in project.items() if k not in ('graph','unknowns','parameters','provenance','layout','modules')},
            **{'models/'+name+'.amua':value for name,value in project.get('modules',{}).items()}}

def pack(project):
    project_budget(project)
    if project.get('modules'):raise WorkflowError('Helper cannot save executable modules without an integrated validated promotion service')
    parts={name:encoded(value) for name,value in components(project).items()}
    manifest={'schema':SCHEMA,'project_id':project['project_id'],'generation_id':project['generation_id'],
              'hashes':{name:digest(data) for name,data in parts.items()},'module_inventory':[]}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(parts.items()):z.writestr(name,data)
        z.writestr('manifest.json',encoded(manifest))
    return out.getvalue()

def unpack(data):
    if len(data)>MAX_PROJECT_BYTES:raise WorkflowError('Project archive exceeds the 12 MiB supported limit')
    with archive(data) as z:
        if sum(i.file_size for i in z.infolist())>MAX_PROJECT_BYTES:raise WorkflowError('Expanded project exceeds the 12 MiB supported limit')
        names=set(z.namelist());manifest=json.loads(z.read('manifest.json'))
        if manifest.get('schema')!=SCHEMA:raise WorkflowError('Unsupported project schema; open recovery copy with a compatible version')
        hashes=manifest.get('hashes',{})
        required={'graph.json','parameters.json','provenance.json','layout.json','project.json'}
        if set(hashes)!=required or names!=required|{'manifest.json'}:raise WorkflowError('Unsupported or missing project components')
        parts={name:z.read(name) for name in hashes}
        if any(digest(parts[name])!=sha for name,sha in hashes.items()):raise WorkflowError('Project component hash mismatch')
        decoded={name:json.loads(value) for name,value in parts.items()}
        project=decoded['project.json'];project.update(decoded['graph.json']);project.update(parameters=decoded['parameters.json'],provenance=decoded['provenance.json'],layout=decoded['layout.json'],modules={})
        if project['generation_id']!=manifest['generation_id'] or project['project_id']!=manifest['project_id']:raise WorkflowError('Project generation identity mismatch')
        validate_graph(project)
        project['session_id']=uid()
        return project

def open_project(path,recover=False):
    path=Path(path)
    try:return unpack(read_project_bytes(path))
    except Exception:
        if not recover:raise
        return unpack(read_project_bytes(path.with_suffix(path.suffix+'.previous')))

def save_project(project,path,expected_hash=None,fault=None):
    path=Path(path).absolute()
    if path.suffix.lower()!='.amuax':raise WorkflowError('Drafts can be saved only as .amuax projects; ordinary .amua export is blocked')
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise WorkflowError('Symlink destinations are unsupported')
    path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_suffix(path.suffix+'.lock')
    if lock.is_symlink():raise WorkflowError('Symlink lock is unsupported')
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd);raise WorkflowError('Project is locked by another writer; save a copy')
    stage=None
    def check(point):
        if fault==point:raise OSError('Injected save failure: '+point)
    try:
        os.ftruncate(fd,0);os.write(fd,encoded({'pid':os.getpid(),'operation':uid()}));os.fsync(fd)
        previous=read_project_bytes(path) if path.exists() else None
        current=digest(previous) if previous is not None else None
        if current!=expected_hash:raise WorkflowError('Destination changed or overwrite not reviewed; save a copy')
        if previous is not None:unpack(previous)
        check('snapshot');generation=copy.deepcopy(project);generation['generation_id']=uid();data=pack(generation)
        handle,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent);stage=Path(name)
        with os.fdopen(handle,'wb') as out:out.write(data);out.flush();check('flush');os.fsync(out.fileno())
        check('verify');unpack(stage.read_bytes())
        if previous is not None:
            backup=path.with_suffix(path.suffix+'.previous')
            bfd,bname=tempfile.mkstemp(prefix='.backup.',dir=path.parent)
            try:
                with os.fdopen(bfd,'wb') as out:out.write(previous);out.flush();os.fsync(out.fileno())
                unpack(Path(bname).read_bytes());os.replace(bname,backup)
            finally:
                if Path(bname).exists():Path(bname).unlink()
        check('backup')
        # Detect writers which ignored our local lock before final publication.
        now=digest(path.read_bytes()) if path.exists() else None
        if now!=current:raise WorkflowError('Conflicting writer changed destination')
        os.replace(stage,path);stage=None;check('publish')
        if os.name!='nt':
            directory=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        check('directory-sync');unpack(path.read_bytes())
        return {'sha256':digest(data),'bytes':len(data),'generation_id':generation['generation_id'],'durability':('file fsync + verified replace; Windows directory power-loss durability not established' if os.name=='nt' else 'tested local atomic replace + fsync; no network/cloud filesystem guarantee')}
    finally:
        os.close(fd)
        if stage and stage.exists():stage.unlink()
        # Keep the inode: unlinking an advisory lock permits two independent writers.

def additive(modules,period):
    relevant=[m for m in modules if period in m['periods']]
    bases={(m['currency'],m['currency_year'],m['perspective'],period) for m in relevant}
    if len(bases)>1:raise WorkflowError('Incompatible currency/year/perspective bases')
    ids=[m['allocation_id'] for m in relevant]
    if len(set(ids))!=len(ids):raise WorkflowError('Duplicate cost allocation')
    total=Decimal(0)
    for m in relevant:
        if m['unit']!='LKR':raise WorkflowError('Incompatible accounting unit')
        cost=Decimal(str(m['unit_cost']));population=Decimal(str(m['population']))
        if not cost.is_finite() or not population.is_finite():raise WorkflowError('Non-finite quantity')
        total+=cost*population
    return total

def shared_draw_demo(values=(1,3)):
    totals=[Decimal(10)*Decimal(z)+Decimal(100)*Decimal(z)+50 for z in values]
    mean=sum(totals)/len(totals);variance=sum((x-mean)**2 for x in totals)/len(totals)
    return {'totals':[str(x) for x in totals],'mean':str(mean),'population_variance':str(variance),'scope':'finite synthetic shared-parameter oracle; not general project PSA'}

def synthetic_project():
    """Declared synthetic fixture; no workbook names or real clinical inputs."""
    source={'id':uid(),'name':'Synthetic additive accounting fixture','kind':'synthetic','sha256':digest(b'cohorts 10,100; costs 2,3; overhead 50; v1'),'bytes':0}
    root=uid();nodes=[{'id':root,'label':'Synthetic programme — first-year budget subtotal','parent':None,'relationship':'presentation','terminal':False,'source_ids':[source['id']]}]
    for label in ['A: 10 facilities × 2 LKR','B: 100 patients × 3 LKR','Shared overhead: 50 LKR once']:
        nodes.append({'id':uid(),'label':label,'parent':root,'relationship':'additive-module','terminal':True,'source_ids':[source['id']]})
    return {'schema':SCHEMA,'project_id':uid(),'generation_id':uid(),'revision':0,'geometry_revision':0,'session_id':uid(),'state':'draft_incomplete',
            'source_set_hash':source['sha256'],'graph':{'nodes':nodes},'unknowns':[question('Enter a synthetic comparator total to enable the comparison demonstration.','number','LKR',[root],source['id'])],
            'parameters':{'synthetic_fixture':True,'facilities':10,'facility_cost':2,'patients':100,'patient_cost':3,'overhead':50},'modules':{},'layout':{},
            'provenance':{'files':[source],'coverage':[{'source_id':source['id'],'status':'included','reason':'Explicit synthetic arithmetic fixture'}],
                          'assumptions':[{'basis':'Synthetic values only; accounting is not a clinical comparison'}],'review':{'domain':'not applicable; synthetic engineering fixture'},'exclusions':[]},'results':[]}

def synthetic_preview(project):
    """Propose a legacy-compatible isolated module; caller must validate in engine.

    The cost subtotal does not depend on the unanswered comparator. Comparison
    remains blocked unless the numeric answer is explicitly reviewed elsewhere.
    """
    validate_graph(project)
    p=project.get('parameters',{})
    if p.get('synthetic_fixture') is not True or any(f['kind']!='synthetic' for f in project['provenance']['files']):raise WorkflowError('Synthetic preview is available only for the explicit synthetic fixture')
    values=[]
    for key in ('facilities','facility_cost','patients','patient_cost','overhead'):
        try:value=Decimal(str(p[key]))
        except Exception:raise WorkflowError('Invalid synthetic quantity')
        if not value.is_finite() or value<0:raise WorkflowError('Invalid synthetic quantity')
        values.append(value)
    facilities,facility_cost,patients,patient_cost,overhead=values
    total=facilities*facility_cost+patients*patient_cost+overhead
    model=ET.Element('Model')
    def field(parent,name,value):ET.SubElement(parent,name).text=str(value)
    field(model,'name','Synthetic first-year budget subtotal — scoped module')
    field(model,'type',0)
    metadata=ET.SubElement(model,'Metadata')
    for key,value in {'author':'Dr. Rejinten Jayawardhana','dateCreated':'2026-11-15','versionCreated':'0.3.6','modifier':'Amua v2.1 synthetic demonstrator','dateModified':'2026-11-15','versionModified':'0.3.6'}.items():field(metadata,key,value)
    dim=ET.SubElement(model,'DimInfo')
    for key,value in {'dimNames':'Cost LKR','dimSymbols':'LKR','decimals':4,'analysisType':0,'objective':0,'objectiveDim':0,'costDim':0,'effectDim':0,'WTP':'0.0','extendedDim':0}.items():field(dim,key,value)
    for key,value in {'scale':100,'alignRight':'false','simParamSets':'false','simType':0,'cohortSize':1,'CRN':'true','crnSeed':1234,'displayIndResults':'false','numThreads':1,'reportSubgroups':'false'}.items():field(model,key,value)
    tree=ET.SubElement(model,'tree')
    for index,name in enumerate(['Synthetic accounting (LKR; first-year)','A + B + once-only overhead']):
        node=ET.SubElement(tree,'Node')
        fields={'type':0 if index==0 else 2,'name':name,'xPos':100+300*index,'yPos':100,'width':20,'height':20,'parentX':0 if index==0 else 120,'parentY':0 if index==0 else 110,'parentType':0,'level':index,
                'hasCost':'false','hasVarUpdates':'false','visible':'true','collapsed':'false','prob':1,'cost':0,'payoff':0 if index==0 else str(total),
                'notes':'Explicit synthetic first-year aggregate only; comparator and cost effectiveness excluded. Adapted and developed by Dr. Rejinten Jayawardhana. Based on the original Amua software by Zachary J. Ward.'}
        for key,value in fields.items():field(node,key,value)
        if index==0:field(node,'childIndices',1)
    data=ET.tostring(model,encoding='utf-8',xml_declaration=True)
    return {'candidate_xml':data.decode('utf-8'),'candidate_hash':digest(data),'expected_total_lkr':str(total),'scope':'Synthetic first-year budget subtotal only; no comparator or health effects',
            'engine_validation':'required before promotion/export','comparison_status':'blocked; typed comparator answer requires review','shared_draw_demo':shared_draw_demo()}

def graph_paths(project):
    """Multiplicity-preserving complete leaf paths, separate from numerical claims."""
    validate_graph(project)
    nodes={n['id']:n for n in project['graph']['nodes']};paths=[]
    for node in nodes.values():
        if not node.get('terminal'):continue
        path=[];current=node
        while current:
            path.append(current['label']);current=nodes.get(current['parent'])
        paths.append(tuple(reversed(path)))
    return Counter(paths)

def reconcile_source_manifests(expected,current):
    """Compare source identity and extracted records against independent inventory.

    This requires an independently retained expected manifest; a ledger generated
    from the current extraction alone is not an independent completeness oracle.
    """
    def facts(project):
        result={}
        for source in project['provenance']['files']:
            prefix=(source['selection_index'] if 'selection_index' in source else source['id'],source['name'])
            result[prefix+('file',)] = source['sha256']
            for sheet in source.get('sheets',[]):
                result[prefix+('sheet',sheet['name'])]=sheet['state']
                for c in sheet['cells']:
                    result[prefix+('cell',sheet['name'],c['cell'])]=digest(encoded({k:v for k,v in c.items() if k!='id'}))
            for part in source.get('parts',[]):result[prefix+('part',part['name'])]=part['sha256']
        return result
    a=facts(expected);b=facts(current)
    return {'missing':[list(k) for k in sorted(a.keys()-b.keys(),key=str)],'unsupported_additions':[list(k) for k in sorted(b.keys()-a.keys(),key=str)],
            'changed':[list(k) for k in sorted(a.keys()&b.keys(),key=str) if a[k]!=b[k]],'complete':a==b}

def change_parameter(project,name,value,expected_revision):
    if project['revision']!=expected_revision:raise WorkflowError('Stale project revision')
    if name not in project['parameters'] or name=='synthetic_fixture':raise WorkflowError('Unknown or protected parameter')
    number=Decimal(str(value))
    if not number.is_finite():raise WorkflowError('Finite parameter required')
    project['parameters'][name]=str(number);project['revision']+=1;project['state']='draft_incomplete'
    for result in project['results']:
        if name in result.get('parameters',[]):result['stale']=True
    return project

def compare_costs(programme,comparator):
    if comparator is None:raise WorkflowError('Comparator is unknown; incremental calculations are blocked')
    a=Decimal(str(programme));b=Decimal(str(comparator))
    if not a.is_finite() or not b.is_finite():raise WorkflowError('Costs must be finite')
    return a-b

def source_scope_draft(project):
    """Expose all inventoried workbook cells and drawing facts without inferring science.

    Edges are explicitly source-record containment or conservative formula
    dependencies. They are never interpreted as engine chance/decision edges.
    """
    nodes=[];dependency_edges=[]
    def add(label,parent,source_ids,**extra):
        node={'id':uid(),'label':label,'parent':parent,'relationship':'source-record','terminal':False,'source_ids':source_ids}
        node.update(extra);nodes.append(node);return node['id']
    root=add('Complete selected source scope — scientific pathways unresolved',None,[])
    questions=[];cell_to_node={}
    for f in project['provenance']['files']:
        fp=add(f['name'],root,[f['id']])
        if f['kind']!='workbook':
            for record in f.get('records',[]):add(str(record['line'])+': '+record['text'],fp,[record['id']],terminal=True)
            for page in f.get('pages',[]):add('Page '+str(page['page'])+' — '+page['status'],fp,[page['id']],terminal=True,extraction_status=page['status'])
            for part in f.get('parts',[]):add('Package part: '+part['name'],fp,[part['id']],terminal=True)
            for region in f.get('regions',[]):add('Image region — visual interpretation unresolved',fp,[region['id']],terminal=True)
            if f.get('parse_issues') or f.get('media_parts') or f.get('images') or f.get('extraction_status')=='incomplete' or f['kind'] in ('parse-error','unsupported'):
                questions.append(question('Resolve unreadable, unsupported or failed source regions before claiming complete coverage.','mapping','source region disposition',[fp],f['id']))
            continue
        cell_names={c['id']:s['name']+'!'+c['cell'] for s in f['sheets'] for c in s['cells']}
        for sheet in f['sheets']:
            sp=add(sheet['name']+(' [hidden]' if sheet['state']!='visible' else ''),fp,[sheet['id']]);rows={}
            for cell in sheet['cells']:
                row=re.search(r'[0-9]+$',cell['cell']).group()
                if row not in rows:rows[row]=add('Row '+row,sp,[sheet['id']])
                detail='='+cell['effective_formula'] if cell['effective_formula'] else str(cell['cached_value'] or '[empty physical record]')
                label=cell['cell']+': '+detail
                if cell['value_kind']=='source-error':label+=' [cached source error]'
                cell_to_node[cell['id']]=add(label,rows[row],[cell['id']],terminal=True,record_kind=cell['value_kind'],formula=cell['effective_formula'],cached_value=cell['cached_value'],scientific_status='uninterpreted source fact')
        drawings=[p for p in f['drawing_parts'] if p['name'].endswith('.xml')]
        if drawings:
            dp=add('Workbook drawings — visual connectors require review',fp,[f['id']])
            for part in drawings:
                partnode=add(part['name'],dp,[part['id']],raw_part_hash=part['sha256'])
                content=part.get('extracted_xml')
                if content:
                    drawing=xml(content.encode())
                    texts=[e.text for e in drawing.iter() if e.tag.rsplit('}',1)[-1]=='t' and e.text]
                    for index,text in enumerate(texts):add(str(index+1)+': '+text,partnode,[part['id']],terminal=True,region_status='text extraction only; geometry/connectors preserved in extracted drawing XML')
                add('Connector/geometry ancestry unresolved; no clinical direction inferred',partnode,[part['id']],terminal=True)
            questions.append(question('Review drawing regions, connectors and their intended scientific ancestry; extracted text alone does not establish pathways.','mapping','drawing regions',[dp],f['id']))
        reverse=defaultdict(set)
        for a,b in f['dependencies']['edges']:
            reverse[a].add(b)
            if a in cell_to_node and b in cell_to_node:dependency_edges.append({'from':cell_to_node[a],'to':cell_to_node[b],'relationship':'conservative-formula-dependency','source_ids':[a,b]})
        for cell_id in f['dependencies']['error_roots']:
            affected={cell_id};queue=deque([cell_id])
            while queue:
                for nxt in reverse[queue.popleft()]:
                    if nxt not in affected:affected.add(nxt);queue.append(nxt)
            q=question('Correct source reference/cache error at '+cell_names[cell_id]+' and confirm recalculation basis.','mapping','corrected cell references',[cell_to_node[x] for x in sorted(affected) if x in cell_to_node],cell_id)
            q['dependency_scope']='Conservative A1 dependency closure; named/dynamic/structured semantics remain unresolved'
            q['affected_source_records']=sorted(affected);questions.append(q)
        for text in ['Confirm screening, confirmation, follow-up, attendance, test characteristics, stage and mortality interpretations against source cells.','Select authoritative cost sheet and reconcile Final Calculations.','Confirm time horizon, population, outcome units and comparator assumptions before calculations.','Review all source-record dispositions and unsupported formula dependencies.']:
            questions.append(question(text,'mapping','declared scientific basis',[fp],f['id']))
    project['graph']={'nodes':nodes,'dependency_edges':dependency_edges,'scope':'complete selected physical source facts; scientific/semantic pathway assembly remains unresolved'}
    project['unknowns']=questions;project['revision']+=1;project['state']='draft_incomplete'
    validate_graph(project)
    return project

def build_chunk_ledger(project,text_budget_tokens=16000,reserved_tokens=4000):
    """Deterministic pending digest chunks; estimated text only, no transmission.

    Images require separately verified provider cost/capability and are never
    represented as having been semantically processed by this digest.
    """
    if not 1024<=text_budget_tokens<=16000 or not 0<=reserved_tokens<text_budget_tokens:raise WorkflowError('Unsupported local request budget')
    char_budget=(text_budget_tokens-reserved_tokens)*4
    records=[]
    for f in project['provenance']['files']:
        records.append({'source_id':f['id'],'kind':f['kind'],'name':f['name'],'sha256':f['sha256']})
        for sheet in f.get('sheets',[]):
            records.append({'source_id':sheet['id'],'sheet':sheet['name'],'state':sheet['state']})
            for cell in sheet['cells']:
                records.append({'source_id':cell['id'],'sheet':sheet['name'],'cell':cell['cell'],'cached_value':cell['cached_value'],'effective_formula':cell['effective_formula'],'status':cell['value_kind']})
        for part in f.get('parts',[]):records.append({'source_id':part['id'],'package_part':part['name'],'sha256':part['sha256'],'status':'physical inventory; semantic review pending'})
        for rec in f.get('records',[]):records.append({'source_id':rec['id'],**{key:value for key,value in rec.items() if key!='id'}})
        for region in f.get('regions',[]):records.append({'source_id':region['id'],'bounds':region['bounds'],'status':'image interpretation pending; no visual inference in text digest'})
        for page in f.get('pages',[]):records.append({'source_id':page['id'],'page':page['page'],'status':page['status'],'text_records':'see associated page text records; no page omitted'})
        for rel in f.get('relationships',[]):
            if 'id' in rel:records.append({'source_id':rel['id'],'relationship':{k:v for k,v in rel.items() if k!='id'}})
    chunks=[];current=[];size=0
    def finish():
        if current:
            payload=encoded(current);chunks.append({'id':sid(project['source_set_hash'],digest(payload)),'sha256':digest(payload),'source_ids':[r['source_id'] for r in current],'status':'pending','estimated_text_tokens':(len(payload)+3)//4,'records':list(current)})
    for record in records:
        length=len(encoded(record))+1
        if length>char_budget:raise WorkflowError('A source record exceeds the chunk budget; explicit incomplete state required')
        if size+length>char_budget:finish();current=[];size=0
        current.append(record);size+=length
    finish()
    project['provenance']['chunks']={'text_budget_tokens':text_budget_tokens,'reserved_tokens':reserved_tokens,'provider_capability':'unverified; no transmission authorized by creating digest','chunks':chunks}
    return project
