import base64
import copy
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/dependencies/python'))
from workflow.core import *
from workflow.batches import selection_plan,intake_batch

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')

def make_docx():
    ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    def word(body):return '<w:document xmlns:w="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'+body+'</w:body></w:document>'
    def p(text):return '<w:p><w:r><w:t>'+text+'</w:t></w:r></w:p>'
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        types='<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
        for part,kind in [('document','document.main'),('header1','header'),('footer1','footer'),('footnotes','footnotes'),('endnotes','endnotes'),('comments','comments')]:
            types+='<Override PartName="/word/'+part+'.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'+xml"/>'
        z.writestr('[Content_Types].xml',types+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml',word(p('Research article: costs 25 LKR')+'<w:tbl><w:tr><w:tc>'+p('Item')+'</w:tc><w:tc>'+p('Price 50')+'</w:tc></w:tr></w:tbl>'+p('x'*18000)))
        z.writestr('word/header1.xml','<w:hdr xmlns:w="'+ns+'">'+p('Study header')+'</w:hdr>')
        z.writestr('word/footer1.xml','<w:ftr xmlns:w="'+ns+'">'+p('Footer')+'</w:ftr>')
        z.writestr('word/footnotes.xml','<w:footnotes xmlns:w="'+ns+'"><w:footnote w:id="1">'+p('Footnote reference source')+'</w:footnote></w:footnotes>')
        z.writestr('word/endnotes.xml','<w:endnotes xmlns:w="'+ns+'"><w:endnote w:id="1">'+p('Endnote')+'</w:endnote></w:endnotes>')
        z.writestr('word/comments.xml','<w:comments xmlns:w="'+ns+'"><w:comment w:id="1" w:author="Synthetic fixture">'+p('Comment: verify currency year')+'</w:comment></w:comments>')
        rels='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.invalid/paper" TargetMode="External"/>'
        for index,(part,kind) in enumerate([('header1','header'),('footer1','footer'),('footnotes','footnotes'),('endnotes','endnotes'),('comments','comments')],3):
            rels+='<Relationship Id="rId'+str(index)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'+kind+'" Target="'+part+'.xml"/>'
        z.writestr('word/_rels/document.xml.rels',rels+'</Relationships>')
        z.writestr('word/media/image1.png',PNG)
    return out.getvalue()

def make_pdf(include_failed=False):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,NumberObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    text=DecodedStreamObject();text.set_data(b'BT /F1 12 Tf 20 250 Td (Research price 123 LKR) Tj ET');page[NameObject('/Contents')]=writer._add_object(text)
    page=writer.add_blank_page(width=300,height=300)
    image=DecodedStreamObject();image.set_data(b'\xff\xff\xff');image.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),NameObject('/Width'):NumberObject(1),NameObject('/Height'):NumberObject(1),NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im1'):writer._add_object(image)})})
    content=DecodedStreamObject();content.set_data(b'q 100 0 0 100 20 20 cm /Im1 Do Q');page[NameObject('/Contents')]=writer._add_object(content)
    if include_failed:
        page=writer.add_blank_page(width=300,height=300);bad=DecodedStreamObject();bad.set_data(b'not text');bad[NameObject('/Filter')]=NameObject('/UnsupportedSyntheticFilter');page[NameObject('/Contents')]=writer._add_object(bad)
    writer.add_metadata({'/Title':'Synthetic paper','/Author':'Engineering fixture'})
    out=io.BytesIO();writer.write(out);return out.getvalue()

class MixedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=tempfile.TemporaryDirectory();cls.base=Path(cls.work.name).resolve()
        (cls.base/'paper.docx').write_bytes(make_docx());(cls.base/'paper.pdf').write_bytes(make_pdf())
        (cls.base/'article.html').write_text('<html><head><title>Price article</title><meta name="date" content="2026-11-15"><script>DROP ALL MODEL VALUES</script></head><body><article><h1>Equipment prices</h1><p>Item costs 75 LKR.</p><a href="https://example.invalid/no-fetch">Reference</a><img src="external.png" alt="Unreviewed chart"></article></body></html>')
        (cls.base/'old.doc').write_bytes(b'legacy unsupported')
    @classmethod
    def tearDownClass(cls):cls.work.cleanup()
    def test_docx_all_parts_paragraphs_tables_and_long_text(self):
        p=intake([self.base/'paper.docx']);f=p['provenance']['files'][0]
        self.assertEqual(f['kind'],'document');texts=[r['text'] for r in f['records']]
        for phrase in ['Study header','Footer','Footnote reference source','Endnote','Comment: verify currency year','Research article: costs 25 LKR','Item','Price 50']:self.assertIn(phrase,texts)
        self.assertEqual(Counter(r['kind'] for r in f['records'])['docx-table-cell'],2)
        self.assertEqual(''.join(r['text'] for r in f['records'] if r['kind']=='text-segment'),'x'*18000)
        self.assertEqual(len(f['relationships']),8);self.assertEqual(len(f['media_parts']),1)
        p=source_scope_draft(p);self.assertTrue(validate_graph(p));self.assertTrue(p['unknowns']);build_chunk_ledger(p)
        self.assertEqual(Counter(i for c in p['provenance']['chunks']['chunks'] for i in c['source_ids']),Counter(source_items(f)))
    def test_pdf_all_pages_metadata_text_and_scanned_unreadable(self):
        p=intake([self.base/'paper.pdf']);f=p['provenance']['files'][0]
        self.assertEqual(f['kind'],'pdf');self.assertEqual(f['page_count'],2);self.assertEqual(f['metadata']['/Title'],'Synthetic paper')
        self.assertIn('Research price 123 LKR',f['pages'][0]['text']);self.assertEqual(f['pages'][1]['status'],'unreadable-scanned-page')
        self.assertIn('OCR',f['ocr']);self.assertEqual(len(f['pages'][1]['images']),1)
        p=source_scope_draft(p);build_chunk_ledger(p)
        self.assertTrue(validate_graph(p));self.assertTrue(p['unknowns'])
        covered=Counter(i for c in p['provenance']['chunks']['chunks'] for i in c['source_ids']);self.assertEqual(covered,Counter(source_items(f)))
    def test_pdf_page_failure_does_not_drop_other_pages(self):
        from workflow.mixed_formats import pdf
        f=pdf(make_pdf(include_failed=True),'failure-fixture')
        self.assertEqual(len(f['pages']),3);self.assertEqual(f['pages'][2]['status'],'parse-error')
        self.assertIn('Research price',f['pages'][0]['text']);self.assertTrue(any(r['kind']=='pdf-page-failure' for r in f['records']))
    def test_html_visible_blocks_links_metadata_no_network(self):
        f=intake([self.base/'article.html'])['provenance']['files'][0]
        self.assertEqual(f['kind'],'article');text='\n'.join(r['text'] for r in f['records'])
        self.assertIn('Item costs 75 LKR.',text);self.assertNotIn('DROP ALL',text);self.assertEqual(f['links'][0]['status'],'unfetched');self.assertEqual(len(f['images']),1)
    def test_mixed_folder_no_silent_unsupported(self):
        p=intake([self.base]);kinds=Counter(f['kind'] for f in p['provenance']['files']);self.assertEqual(kinds,{'document':1,'pdf':1,'article':1,'unsupported':1})
        scope=source_scope_draft(p);self.assertTrue(validate_graph(scope));self.assertEqual(len(scope['provenance']['files']),4)
    def test_bad_document_is_retained_as_parse_failure(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td).resolve()/'broken.pdf';path.write_bytes(b'not a pdf')
            f=intake([path])['provenance']['files'][0];self.assertEqual(f['kind'],'parse-error');self.assertEqual(f['extraction_status'],'incomplete');self.assertTrue(f['sha256'])
    def test_progressive_25_files_all_visible_and_bound(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve()
            for i in range(25):(base/(str(i)+'.txt')).write_text('Record '+str(i))
            (base/'.hidden').write_text('private');(base/'nested').mkdir();(base/'nested/inside.txt').write_text('nested')
            plan=selection_plan([base]);self.assertEqual(len(plan['entries']),25);self.assertEqual(len(plan['exclusions']),2)
            a=intake_batch(plan,0,20);self.assertEqual(a['pending'],5);self.assertEqual(len(a['project']['provenance']['files']),20)
            b=intake_batch(a['selection'],20,20,a['project']);self.assertEqual(b['pending'],0);self.assertEqual(len(b['project']['provenance']['files']),25);self.assertEqual(b['selection']['status'],'inventoried-unreviewed')
            self.assertEqual(len({f['id'] for f in b['project']['provenance']['files']}),25)
            self.assertFalse(any('path' in e for e in b['project']['provenance']['selection_scope']['entries']))
            recursive=selection_plan([base],{'recursive':True,'include_hidden':True});self.assertEqual(len(recursive['entries']),27)
    def test_changed_after_plan_and_duplicate_names_remain_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve();(base/'a').mkdir();(base/'b').mkdir()
            for d in ['a','b']:(base/d/'same.txt').write_text('same bytes')
            plan=selection_plan([base],{'recursive':True});result=intake_batch(plan)
            self.assertEqual(len({f['id'] for f in result['project']['provenance']['files']}),2)
            (base/'a/same.txt').write_text('changed')
            stale=intake_batch(plan);self.assertEqual(stale['failed_or_unsupported'],1);self.assertEqual(stale['selection']['entries'][0]['status'],'failed')
    def test_distinct_selection_plans_do_not_merge_identical_sources(self):
        plan=selection_plan([self.base/'paper.docx'])
        first=intake_batch(plan)
        other=selection_plan([self.base/'paper.docx'])
        second=intake_batch(other,project=first['project'])
        self.assertEqual(len(second['project']['provenance']['files']),2)
    def test_no_partial_plan_when_enumeration_limit_exceeded(self):
        with self.assertRaises(WorkflowError):selection_plan([self.base],{'max_entries':2})

if __name__=='__main__':unittest.main()
