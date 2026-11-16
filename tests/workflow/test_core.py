import copy
import io
import json
import sys
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path
from workflow.core import *

ROOT=Path(__file__).resolve().parents[2]
INPUTS=ROOT/'evidence/inputs'

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (INPUTS/'D2P cost analysis Cluster care.xlsx').exists():raise unittest.SkipTest('Private scientific acceptance workbooks/images are not distributed; see public intake tests')
        cls.d2p=intake([INPUTS/'D2P cost analysis Cluster care.xlsx',ROOT/'evidence/prior/d2p_tree_v2.png',ROOT/'evidence/prior/d2p_tree.png'])
        cls.ckd=intake([INPUTS/'CKD Decision Tree WITH SENSITIVITY ANALYSIS.xlsx'])
    def test_real_inventories(self):
        d=self.d2p['provenance']['files'][0];c=self.ckd['provenance']['files'][0]
        self.assertEqual([s['name'] for s in d['sheets']],['Data Sheet','Upfront & 1 year cost','Recurrent for 1 year'])
        for book,counts in [(d,(3,520,494,175,29,0)),(c,(6,2269,1555,654,53,24))]:
            cells=[x for s in book['sheets'] for x in s['cells']]
            self.assertEqual((len(book['sheets']),len(cells),sum(x['has_value_formula_inline'] for x in cells),sum(x['formula'] is not None for x in cells),sum(x['formula_attributes'].get('t')=='shared' for x in cells),sum(x['value_kind']=='source-error' for x in cells)),counts)
        self.assertTrue(c['drawing_parts']);self.assertTrue(c['media_parts'])
    def test_shared_formulas(self):
        d=self.d2p['provenance']['files'][0]
        index={(s['name'],c['cell']):c for s in d['sheets'] for c in s['cells']}
        for sheet,cell,formula in [('Upfront & 1 year cost','E14','C14*D14'),('Upfront & 1 year cost','E15','C15*D15'),('Recurrent for 1 year','E12','C12*D12')]:self.assertEqual(index[sheet,cell]['effective_formula'],formula)
        self.assertEqual(translate_formula('SUM($A1,B$2,"C3")','D4','E5'),'SUM($A2,C$2,"C3")')
    def test_error_closure_includes_roots_and_dependents(self):
        c=self.ckd['provenance']['files'][0]
        roots=set(c['dependencies']['error_roots']);closure=set(c['dependencies']['affected_error_closure'])
        self.assertTrue(roots<=closure);self.assertGreaterEqual(len(closure),24)
        for sheet,address in [('CKD Intervention','V6'),('Status Quo New','X16')]:
            cell=next(c for s in c['sheets'] if s['name']==sheet for c in s['cells'] if c['cell']==address)
            self.assertIn(cell['id'],roots)
    def test_d2p_full_paths(self):
        p=d2p_draft(copy.deepcopy(self.d2p));nodes=p['graph']['nodes']
        self.assertEqual(Counter(n['module'] for n in nodes if n['terminal'] and n['module']),{'A':18,'B':6,'C':2})
        parents={n['id']:n for n in nodes}
        paths=[]
        for n in nodes:
            if n['terminal']:
                labels=[n['label']];cur=n
                while cur['parent']:
                    cur=parents[cur['parent']];labels.append(cur['label'])
                paths.append(tuple(reversed(labels)))
        self.assertEqual(len(paths),len(set(paths)));self.assertEqual(len(p['graph']['programme_ledger']),10)
        self.assertEqual(len([n for n in nodes if n.get('components')]),2)
        self.assertTrue(validate_graph(p))
    def test_coverage_and_citation_mutations(self):
        p=copy.deepcopy(self.d2p);p['provenance']['coverage'].pop()
        with self.assertRaises(WorkflowError):validate_graph(p)
        p=copy.deepcopy(self.d2p);p['graph']['nodes'][0]['source_ids']=['made-up']
        with self.assertRaises(WorkflowError):validate_graph(p)
        p=copy.deepcopy(self.d2p);p['graph']['nodes'][1]['parent']=p['graph']['nodes'][1]['id']
        with self.assertRaises(WorkflowError):validate_graph(p)
    def test_portable_save_reopen_and_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td).resolve()/'draft.amuax';p=d2p_draft(copy.deepcopy(self.d2p));first=save_project(p,path)
            reopened=open_project(path);self.assertEqual(p['graph'],reopened['graph']);self.assertEqual(p['provenance'],reopened['provenance'])
            self.assertFalse(reopened['modules']);p['revision']+=1;p['generation_id']=uid()
            with self.assertRaises(WorkflowError):save_project(p,path)
            second=save_project(p,path,first['sha256']);self.assertNotEqual(first['sha256'],second['sha256'])
            self.assertEqual(open_project(path.with_suffix('.amuax.previous'))['revision'],1)
            path.write_bytes(b'broken');self.assertEqual(open_project(path,recover=True)['revision'],1)
    def test_faults_preserve_valid_generation(self):
        for boundary in ['snapshot','flush','verify','backup','publish','directory-sync']:
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as td:
                path=Path(td).resolve()/'x.amuax';p=copy.deepcopy(self.d2p);first=save_project(p,path)
                p['revision']+=1;p['generation_id']=uid()
                with self.assertRaises(OSError):save_project(p,path,first['sha256'],fault=boundary)
                self.assertIn(open_project(path)['revision'],[0,1])
                if boundary in ('publish','directory-sync'):self.assertEqual(open_project(path.with_suffix('.amuax.previous'))['revision'],0)
                import fcntl
                with path.with_suffix('.amuax.lock').open('r+') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB) # Prior failure released OS lock
    def test_tamper_and_module_barriers(self):
        data=pack(copy.deepcopy(self.d2p))
        with archive(data) as z:
            parts={name:z.read(name) for name in z.namelist()}
        parts['graph.json']=b'{}';out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name,value in parts.items():z.writestr(name,value)
        with self.assertRaises(WorkflowError):unpack(out.getvalue())
        p=copy.deepcopy(self.d2p);p['modules']={'fake':'<amua/>'}
        with self.assertRaises(WorkflowError):pack(p)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(WorkflowError):save_project(self.d2p,Path(td).resolve()/'incomplete.amua')
    def test_archive_traversal_entities(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('../escape','bad')
        with self.assertRaises(WorkflowError):archive(out.getvalue())
        with self.assertRaises(WorkflowError):xml(b'<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><foo/>')
    def test_typed_answers_stale_and_mismatch(self):
        p=copy.deepcopy(self.d2p);q=p['unknowns'][0]
        with self.assertRaises(WorkflowError):answer_question(p,q['id'],'looks fine',q['unit'],p['revision'])
        with self.assertRaises(WorkflowError):answer_question(p,q['id'],{},'wrong',p['revision'])
        rev=p['revision'];answer_question(p,q['id'],{'cost':'confirm'},q['unit'],rev)
        self.assertEqual(q['status'],'answered_pending_review')
        with self.assertRaises(WorkflowError):answer_question(p,q['id'],{},q['unit'],rev)
    def test_additive_and_shared_draw_oracles(self):
        def module(name,n,c,periods=['first-year','recurrent']):return {'allocation_id':name,'population':n,'unit_cost':c,'unit':'LKR','currency':'LKR','currency_year':2026,'perspective':'synthetic','periods':periods}
        modules=[module('A',10,2),module('B',100,3),module('overhead',1,50,['first-year'])]
        self.assertEqual(additive(modules,'first-year'),Decimal(370));self.assertEqual(additive(modules,'recurrent'),Decimal(320))
        with self.assertRaises(WorkflowError):additive(modules+[modules[2]],'first-year')
        modules[0]['unit']='USD'
        with self.assertRaises(WorkflowError):additive(modules,'first-year')
        result=shared_draw_demo();self.assertEqual(result['totals'],['160','380']);self.assertEqual(result['mean'],'270');self.assertEqual(result['population_variance'],'12100')
    def test_bounded_chunk_coverage_and_pending_ledger(self):
        p=build_chunk_ledger(copy.deepcopy(self.ckd));chunks=p['provenance']['chunks']['chunks']
        self.assertGreater(len(chunks),1)
        expected=Counter(x for f in p['provenance']['files'] for x in source_items(f))
        self.assertEqual(Counter(x for c in chunks for x in c['source_ids']),expected)
        self.assertTrue(all(c['status']=='pending' and c['estimated_text_tokens']<=12000 for c in chunks))
        first=[c['sha256'] for c in chunks];build_chunk_ledger(p)
        self.assertEqual(first,[c['sha256'] for c in p['provenance']['chunks']['chunks']])
    def test_complete_ckd_source_scope_and_drawing_uncertainty(self):
        p=source_scope_draft(copy.deepcopy(self.ckd));nodes=p['graph']['nodes']
        cells=[n for n in nodes if 'record_kind' in n]
        self.assertEqual(len(cells),2269)
        self.assertEqual(sum(n['record_kind']=='source-error' for n in cells),24)
        self.assertEqual(len([q for q in p['unknowns'] if 'affected_source_records' in q]),24)
        self.assertTrue(any('Connector/geometry ancestry unresolved' in n['label'] for n in nodes))
        self.assertTrue(all(n['relationship']=='source-record' for n in nodes))
        self.assertEqual(p['state'],'draft_incomplete');self.assertFalse(p['modules'])
    def test_region_hidden_sheet_and_citation_mutations(self):
        expected=copy.deepcopy(self.d2p)
        p=copy.deepcopy(expected);p['provenance']['files'][1]['regions']=[]
        # Removing image interpretation region cannot leave a matching coverage ledger.
        with self.assertRaises(WorkflowError):validate_graph(p)
        p=d2p_draft(copy.deepcopy(expected));p['graph']['nodes'][2]['source_ids']=['corrupt-citation']
        with self.assertRaises(WorkflowError):validate_graph(p)
        p=copy.deepcopy(self.ckd);p['provenance']['files'][0]['sheets'][0]['state']='hidden'
        self.assertTrue(reconcile_source_manifests(self.ckd,p)['changed'])
        p=copy.deepcopy(expected);p['provenance']['files'][1]['sha256']='different-image'
        with self.assertRaises(WorkflowError):d2p_draft(p)
    def test_synthetic_preview_and_parameter_invalidation(self):
        p=synthetic_project();proposal=synthetic_preview(p)
        self.assertEqual(proposal['expected_total_lkr'],'370')
        self.assertEqual(xml(proposal['candidate_xml'].encode()).find('tree/Node/payoff').text,'0')
        p['results']=[{'parameters':['facility_cost'],'stale':False}]
        change_parameter(p,'facility_cost',4,0)
        self.assertTrue(p['results'][0]['stale']);self.assertEqual(synthetic_preview(p)['expected_total_lkr'],'390')
        with self.assertRaises(WorkflowError):compare_costs(370,None)
        self.assertEqual(compare_costs(370,300),70)
    def test_independent_preledger_manifest_and_graph_mutations(self):
        p=copy.deepcopy(self.d2p);p['provenance']['files'][0]['sheets'].pop()
        self.assertFalse(reconcile_source_manifests(self.d2p,p)['complete'])
        p=copy.deepcopy(self.d2p);p['provenance']['files'][0]['sheets'][0]['cells'][0]['cached_value']='999'
        self.assertTrue(reconcile_source_manifests(self.d2p,p)['changed'])
        p=d2p_draft(copy.deepcopy(self.d2p));expected=graph_paths(p)
        leaf=next(n for n in p['graph']['nodes'] if n['module']=='A' and n['terminal'])
        leaf['label']='substituted leaf keeping count'
        self.assertNotEqual(expected,graph_paths(p))
        p=d2p_draft(copy.deepcopy(self.d2p));expected=graph_paths(p)
        leaf=next(n for n in p['graph']['nodes'] if n['module']=='A' and n['terminal'])
        leaf['parent']=next(n['id'] for n in p['graph']['nodes'] if n['label']=='B Digital readiness')
        self.assertNotEqual(expected,graph_paths(p))
    def test_limits_and_duplicate_dependency_reference(self):
        with self.assertRaises(WorkflowError):intake([INPUTS/'D2P cost analysis Cluster care.xlsx']*21)
        sheets=[{'name':'Held Out','cells':[
            {'id':'a','cell':'A1','effective_formula':None,'value_kind':'literal'},
            {'id':'b','cell':'B1','effective_formula':'A1+A1','value_kind':'cached'}]}]
        deps=dependencies(sheets)
        self.assertEqual(deps['edges'],[['a','b']]);self.assertEqual(deps['cycle_or_dependent'],[])
    def test_held_out_hidden_sheet_and_duplicate_names(self):
        # Independent synthetic XLSX, not workbook-name recognition.
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns="'+NS['s']+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Secret" state="hidden" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="'+NS['s']+'"><sheetData><row><c r="A1"><v>7</v></c></row></sheetData></worksheet>')
        book=workbook(out.getvalue(),'synthetic');self.assertEqual(book['sheets'][0]['state'],'hidden');self.assertEqual(book['sheets'][0]['cells'][0]['cached_value'],'7')

if __name__=='__main__':unittest.main()
