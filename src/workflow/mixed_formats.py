"""Deterministic local DOCX, PDF and saved-HTML extraction; no network fetches.

Records are source facts, not scientific classifications. Unsupported or unreadable
regions remain in the inventory, with stable identifiers and explicit status.
"""
import io
import logging
import json
import math
import os
import subprocess
import tempfile
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

from .core import WorkflowError, archive, digest, sid, xml

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MAX_RECORDS=100000
MAX_TEXT=20000000
SEGMENT_CHARS=8000

def record_builder(source_id):
    records=[];text_count=0
    def add(locator,kind,text='',**metadata):
        nonlocal text_count
        text_count+=len(text)
        if text_count>MAX_TEXT or len(records)>=MAX_RECORDS:raise WorkflowError('Document text/record limit exceeded; source remains incomplete')
        identity=sid(source_id,locator)
        # Large source items get an explicit parent plus ordered source-bound
        # segments, so every character is retained within outgoing chunk budgets.
        if len(text)>SEGMENT_CHARS:
            record={'id':identity,'line':len(records)+1,'locator':locator,'kind':kind,'text':'','segmented':True,'character_count':len(text),**metadata}
            records.append(record)
            for start in range(0,len(text),SEGMENT_CHARS):
                records.append({'id':sid(source_id,locator+':characters:'+str(start)),'line':len(records)+1,'locator':locator+':characters:'+str(start),'kind':'text-segment','text':text[start:start+SEGMENT_CHARS],'parent_id':identity,'character_start':start,'character_end':min(start+SEGMENT_CHARS,len(text))})
        else:
            records.append({'id':identity,'line':len(records)+1,'locator':locator,'kind':kind,'text':text,**metadata})
        return identity
    return records,add

def docx(data,source_id):
    records,add=record_builder(source_id)
    parts=[];rels=[];media=[];issues=[]
    with archive(data) as z:
        if 'word/document.xml' not in z.namelist():raise WorkflowError('DOCX document part is missing')
        for info in z.infolist():
            if info.is_dir():continue
            raw=z.read(info);part_id=sid(source_id,'part:'+info.filename)
            part={'id':part_id,'name':info.filename,'bytes':info.file_size,'sha256':digest(raw)};parts.append(part)
            if info.filename.endswith('.rels'):
                try:
                    relationships=[{'id':sid(source_id,info.filename+':'+r.get('Id','')),'part':info.filename,**dict(r.attrib)} for r in xml(raw)]
                    rels.extend(relationships)
                    for rel in relationships:add('relationship:'+rel['part']+':'+rel.get('Id',''),'docx-relationship',rel.get('Target',''),relationship_type=rel.get('Type'),external=rel.get('TargetMode')=='External')
                except Exception:issues.append({'part_id':part_id,'status':'parse-error','reason':'Relationship XML could not be parsed'})
            if info.filename.startswith('word/media/'):
                media.append(part);add('media:'+info.filename,'embedded-image-or-media',info.filename,part_id=part_id,status='unresolved',reason='Media inventoried; visual interpretation has not been performed')
            if not info.filename.startswith('word/') or not info.filename.endswith('.xml'):continue
            try:root=xml(raw)
            except Exception:
                issues.append({'part_id':part_id,'status':'parse-error','reason':'DOCX XML part could not be parsed'});continue
            local=info.filename.rsplit('/',1)[-1]
            content_part=(local=='document.xml' or local.startswith(('header','footer','footnotes','endnotes','comments','glossary')))
            if not content_part:
                # Styles/settings/numbering remain hashed package facts; their
                # complete bounded XML is retained for later format interpretation.
                part['extracted_xml']=ET.tostring(root,encoding='unicode')
                continue
            table_index=0;paragraph_index=0
            def paragraph_text(p):
                output=[]
                def walk(e):
                    if e is not p and e.tag=='{'+W+'}p':return
                    tag=e.tag.rsplit('}',1)[-1]
                    if tag in ('t','delText','instrText'):output.append(e.text or '')
                    elif tag=='tab':output.append('\t')
                    elif tag in ('br','cr'):output.append('\n')
                    for c in e:walk(c)
                walk(p);return ''.join(output)
            paragraph_ids={}
            for e in root.iter():
                if e.tag=='{'+W+'}p':
                    paragraph_index+=1;locator=info.filename+':paragraph:'+str(paragraph_index)
                    statuses=sorted({n.tag.rsplit('}',1)[-1] for n in e.iter() if n.tag.rsplit('}',1)[-1] in ('ins','del','fldSimple','instrText','drawing','pict','footnoteReference','endnoteReference','commentReference')})
                    paragraph_ids[id(e)]=add(locator,'docx-paragraph',paragraph_text(e),part=info.filename,part_id=part_id,xml_features=statuses)
            for e in root.iter('{'+W+'}tbl'):
                table_index+=1;tableloc=info.filename+':table:'+str(table_index)
                tableid=add(tableloc,'docx-table','',part_id=part_id)
                for ri,row in enumerate(e.findall('{'+W+'}tr'),1):
                    rowid=add(tableloc+':row:'+str(ri),'docx-table-row','',parent_id=tableid,row=ri)
                    for ci,cell in enumerate(row.findall('{'+W+'}tc'),1):
                        add(tableloc+':row:'+str(ri)+':cell:'+str(ci),'docx-table-cell','',parent_id=rowid,row=ri,column=ci,paragraph_ids=[paragraph_ids[id(p)] for p in cell.iter('{'+W+'}p')],properties_xml=ET.tostring(cell.find('{'+W+'}tcPr'),encoding='unicode') if cell.find('{'+W+'}tcPr') is not None else None)
            for e in root.iter():
                if e.tag.rsplit('}',1)[-1] in ('altChunk','object'):
                    issues.append({'part_id':part_id,'status':'unsupported','reason':'Embedded object or alternate chunk requires explicit interpretation'})
        return {'kind':'document','document_format':'DOCX','records':records,'parts':parts,'relationships':rels,'media_parts':media,'parse_issues':issues,
                'extraction_status':'incomplete' if issues or media else 'text-extracted-unreviewed','external_content':'never fetched; links retained as source records','tracked_changes':'included as source text/feature flags; no acceptance or rejection inferred'}

def native_ocr_helper():
    """Find only the app-owned helper or this checkout's explicit build tool."""
    location=Path(__file__).resolve()
    candidates=[location.parents[2]/'libexec/amua-ocr',location.parents[2]/'build/tools/amua-ocr']
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate,os.X_OK):return candidate
    return None

class LocalOCR:
    """One private immutable PDF snapshot, reused for bounded local page OCR."""
    def __init__(self,data,helper=None):
        self.data=data;self.helper=native_ocr_helper() if helper is None else (Path(helper) if helper is not False else None);self.snapshot=None
    def __enter__(self):return self
    def __exit__(self,*_):
        if self.snapshot is not None:
            try:self.snapshot.unlink()
            except FileNotFoundError:pass
    def page(self,number):
        if self.helper is None:return {'status':'unsupported','reason_category':'native-helper-unavailable','language':'en-US'}
        if not self.helper.is_absolute() or not self.helper.is_file():return {'status':'unsupported','reason_category':'native-helper-unavailable','language':'en-US'}
        if self.snapshot is None:
            fd,path=tempfile.mkstemp(prefix='amua-ocr-',suffix='.pdf')
            self.snapshot=Path(path)
            with os.fdopen(fd,'wb') as out:
                os.fchmod(out.fileno(),0o600);out.write(self.data);out.flush()
        command=[str(self.helper),'--pdf',str(self.snapshot),'--page',str(number),'--max-pixels','8000000']
        try:
            result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20,env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8'},check=False)
        except subprocess.TimeoutExpired:return {'status':'unsupported','reason_category':'timeout','language':'en-US'}
        except OSError:return {'status':'unsupported','reason_category':'helper-launch-failed','language':'en-US'}
        if len(result.stdout)>4*1024*1024:return {'status':'unsupported','reason_category':'helper-output-limit','language':'en-US'}
        try:reply=json.loads(result.stdout)
        except Exception:return {'status':'unsupported','reason_category':'invalid-helper-reply','language':'en-US'}
        if not isinstance(reply,dict) or reply.get('status') not in ('ok','unreadable','unsupported') or reply.get('page',number)!=number:return {'status':'unsupported','reason_category':'invalid-helper-reply','language':'en-US'}
        text=reply.get('text','');regions=reply.get('regions',[])
        confidence=reply.get('confidence',0)
        if not isinstance(text,str) or len(text)>250000 or not isinstance(regions,list) or len(regions)>5000:return {'status':'unsupported','reason_category':'helper-output-limit','language':'en-US'}
        if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0<=confidence<=1:return {'status':'unsupported','reason_category':'invalid-helper-confidence','language':'en-US'}
        for region in regions:
            if not isinstance(region,dict) or not isinstance(region.get('text',''),str):return {'status':'unsupported','reason_category':'invalid-helper-region','language':'en-US'}
            value=region.get('confidence',0)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:return {'status':'unsupported','reason_category':'invalid-helper-confidence','language':'en-US'}
        if reply.get('language','en-US') not in ('en','en-US'):return {'status':'unsupported','reason_category':'unsupported-language','language':reply.get('language')}
        if result.returncode!=0 and reply.get('status')=='ok':return {'status':'unsupported','reason_category':'helper-failed','language':'en-US'}
        reply['helper']='Apple Vision/PDFKit local English OCR';reply['review_status']='unreviewed; verify recognized values and scientific meaning'
        return reply

def pdf(data,source_id,ocr_helper=None,ocr_start=1,ocr_count=20):
    # Development checkout fallback. The bundle puts this directory's contents
    # directly beside workflow in pythonlib; no system pip dependency is needed.
    vendored=Path(__file__).resolve().parents[1]/'dependencies/python'
    if vendored.is_dir() and str(vendored) not in sys.path:sys.path.insert(0,str(vendored))
    try:
        import pypdf
        from pypdf import PdfReader
        import pypdf.filters
    except ImportError:raise WorkflowError('Bundled PDF parser is unavailable; PDF scope remains unresolved')
    logging.getLogger('pypdf').disabled=True
    pypdf.overwrite_configuration(zlib_maximum_output_length=16*1024*1024,maximum_declared_stream_length=16*1024*1024,array_based_stream_maximum_output_length=16*1024*1024,lzw_maximum_output_length=16*1024*1024,run_length_maximum_output_length=16*1024*1024)
    try:reader=PdfReader(io.BytesIO(data),strict=True)
    except Exception:raise WorkflowError('PDF structure could not be parsed; source remains unresolved')
    if reader.is_encrypted:raise WorkflowError('Encrypted PDF requires an explicitly decrypted local copy; no password guessing')
    try:count=len(reader.pages)
    except Exception:raise WorkflowError('PDF page tree could not be enumerated; source remains unresolved')
    if count>2000:raise WorkflowError('PDF page limit exceeded; split into explicit source-bound batches')
    records,add=record_builder(source_id);pages=[];issues=[]
    try:metadata={str(k):str(v) for k,v in (reader.metadata or {}).items()}
    except Exception:
        metadata={};issues.append({'status':'parse-error','reason':'PDF metadata could not be read; page enumeration retained'})
    add('metadata','pdf-metadata',str(metadata),metadata=metadata)
    if type(ocr_start) is not int or type(ocr_count) is not int or ocr_start<1 or not 1<=ocr_count<=20:raise WorkflowError('OCR page batch requires a start page and 1–20 pages')
    ocr_deadline=time.monotonic()+60
    with LocalOCR(data,ocr_helper) as ocr:
        for number in range(count):
            pageid=sid(source_id,'page:'+str(number+1));item={'id':pageid,'page':number+1,'status':'pending','text':''}
            pages.append(item)
            try:
                page=reader.pages[number];item['bounds']=[float(x) for x in page.mediabox]
                resources=page.get('/Resources',{})
                resources=resources.get_object() if hasattr(resources,'get_object') else resources
                xobjects=resources.get('/XObject',{})
                xobjects=xobjects.get_object() if hasattr(xobjects,'get_object') else xobjects
                images=[]
                for name,obj in xobjects.items():
                    obj=obj.get_object()
                    if obj.get('/Subtype')=='/Image':
                        image={'name':str(name),'width':int(obj.get('/Width',0)),'height':int(obj.get('/Height',0)),'filter':str(obj.get('/Filter','')),'status':'visual-unreviewed'}
                        images.append(image);add('page:'+str(number+1)+':image:'+str(name),'pdf-image','',page=number+1,**image)
                item['images']=images
                contents=page.get_contents()
                if contents is not None and len(contents.get_data())>16*1024*1024:raise WorkflowError('PDF page content expansion limit exceeded')
                text=page.extract_text() or ''
                if len(text)>2000000:raise WorkflowError('PDF page text limit exceeded')
                item['text']=text;item['status']='text-extracted-unreviewed' if text.strip() else ('unreadable-scanned-page' if images else 'empty-or-unreadable-page')
                add('page:'+str(number+1)+':text','pdf-page-text',text,page=number+1,page_id=pageid,status=item['status'])
                for index,annotation in enumerate(page.get('/Annots',[]) or []):
                    a=annotation.get_object()
                    action=a.get('/A',{})
                    if hasattr(action,'get_object'):action=action.get_object()
                    add('page:'+str(number+1)+':annotation:'+str(index),'pdf-annotation',str(a.get('/Contents','')),page=number+1,annotation_subtype=str(a.get('/Subtype','')),uri=str(action.get('/URI','')),status='unreviewed; no action executed')
                if not text.strip():
                    if not ocr_start<=number+1<ocr_start+ocr_count:
                        outcome={'status':'unsupported','reason_category':'ocr-page-batch-pending','text':'','regions':[]}
                    elif time.monotonic()>=ocr_deadline:
                        outcome={'status':'unsupported','reason_category':'ocr-batch-time-budget','text':'','regions':[]}
                    else:outcome=ocr.page(number+1)
                    item['ocr']=outcome
                    if outcome.get('status')=='ok' and outcome.get('text','').strip():
                        item['original_extracted_text']=text;item['text']=outcome['text']
                        item['status']='ocr-extracted-unreviewed' if outcome.get('confidence',0)>=0.8 else 'ocr-low-confidence-unreviewed'
                        add('page:'+str(number+1)+':ocr-text','pdf-page-ocr-text',outcome['text'],page=number+1,page_id=pageid,status=item['status'],confidence=outcome.get('confidence'),language=outcome.get('language','en-US'),transformation='local OCR of rasterized immutable source page; verify all recognized values')
                        for index,region in enumerate(outcome.get('regions',[])):
                            add('page:'+str(number+1)+':ocr-region:'+str(index),'pdf-ocr-region',region.get('text',''),page=number+1,page_id=pageid,bounds=region.get('bounds'),confidence=region.get('confidence'),status='unreviewed')
                        issues.append({'page_id':pageid,'status':item['status'],'reason':'OCR text is provisional. Verify labels, quantities, references and scientific meaning against the page image.'})
                    else:
                        issues.append({'page_id':pageid,'status':item['status'],'reason':'No readable text layer; local OCR did not resolve the page. Review a searchable copy or the image.','ocr_reason':outcome.get('reason_category',outcome.get('status'))})
            except Exception as exc:
                item['status']='parse-error';item['error_category']=type(exc).__name__
                issues.append({'page_id':pageid,'status':'parse-error','reason':'Page could not be extracted; remaining pages are still inventoried'})
                add('page:'+str(number+1)+':failure','pdf-page-failure','Page extraction failed',page=number+1,error_category=type(exc).__name__)
    catalog=reader.trailer.get('/Root',{}).get_object()
    return {'kind':'pdf','document_format':'PDF','parser':'pypdf '+pypdf.__version__,'pages':pages,'records':records,'metadata':metadata,'parse_issues':issues,
            'page_count':count,'extraction_status':'incomplete' if issues else 'text-extracted-unreviewed','ocr':'local English Apple Vision/PDFKit OCR helper where available; recognized text remains unreviewed' if any('ocr' in p and p['ocr'].get('helper') for p in pages) else 'unavailable; no OCR performed','active_content':{'open_action_present':'/OpenAction' in catalog,'names_present':'/Names' in catalog,'executed':False},
            'limitations':['Text order/layout/tables/figures/footnotes require review; extracted text is not proof of semantic completeness','Embedded actions, scripts, attachments and URLs are never executed or fetched']}

class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.records=[];self.suppressed=[];self.stack=[];self.buffer=[];self.context='text';self.links=[];self.images=[];self.metadata=[];self.warnings=[]
    def flush(self):
        text=''.join(self.buffer);self.buffer=[]
        if text.strip():self.records.append((self.context,text))
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript','template'):self.flush();self.suppressed.append(tag)
        if self.suppressed:return
        if tag in ('p','div','section','article','h1','h2','h3','h4','h5','h6','li','tr','td','th','blockquote','title','pre','table'):
            self.flush();self.context=tag
        if tag=='br':self.buffer.append('\n')
        if tag=='a':self.links.append({'href':attrs.get('href',''),'title':attrs.get('title',''),'status':'unfetched'})
        if tag=='img':self.images.append({'src':attrs.get('src',''),'alt':attrs.get('alt',''),'status':'unreadable-unfetched-image'})
        if tag=='meta':self.metadata.append(attrs)
        if tag in ('iframe','object','embed'):self.warnings.append({'tag':tag,'status':'unsupported-unfetched-embedded-content'})
    def handle_endtag(self,tag):
        if self.suppressed:
            if self.suppressed[-1]==tag:self.suppressed.pop()
            return
        if tag in ('p','div','section','article','h1','h2','h3','h4','h5','h6','li','tr','td','th','blockquote','title','pre','table'):self.flush()
    def handle_data(self,data):
        if not self.suppressed:self.buffer.append(data)

def html_article(data,source_id):
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:
        # Honour a declared local byte encoding without browser/network execution.
        declaration=re.search(br'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',data[:8192],re.I)
        if declaration is None:raise WorkflowError('HTML encoding is unreadable; save a UTF-8 local copy')
        try:text=data.decode(declaration.group(1).decode('ascii'))
        except Exception:raise WorkflowError('Declared HTML encoding could not be decoded')
    parser=ArticleParser();parser.feed(text);parser.close();parser.flush()
    records,add=record_builder(source_id)
    for index,(tag,value) in enumerate(parser.records,1):add('block:'+str(index),'html-'+tag,value)
    for index,link in enumerate(parser.links,1):add('link:'+str(index),'html-link',link['href'],**link)
    for index,image in enumerate(parser.images,1):add('image:'+str(index),'html-image',image['alt'],**image)
    for index,meta in enumerate(parser.metadata,1):add('metadata:'+str(index),'html-metadata',str(meta),attributes=meta)
    return {'kind':'article','document_format':'HTML','records':records,'links':parser.links,'images':parser.images,'metadata':parser.metadata,
            'parse_issues':parser.warnings,'extraction_status':'text-extracted-unreviewed','network':'none; scripts/styles omitted from prose, external resources never fetched','limitations':['CSS visibility and visual ancestry are not evaluated','HTML tables preserved as ordered text blocks; complex spans require review']}
