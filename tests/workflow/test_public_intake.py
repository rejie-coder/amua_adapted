"""Public fixture coverage of intake/guard/persistence without private scientific data."""
import copy,io,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from public_fixtures import workbook
from workflow.core import intake,validate_graph,save_project,open_project,WorkflowError,translate_formula,source_scope_draft,source_items,xml,archive,uid
class PublicIntakeTests(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.folder=Path(self.temporary.name).resolve();self.source=workbook(self.folder);self.project=intake([self.source])
 def test_full_synthetic_workbook_inventory(self):
  file=self.project['provenance']['files'][0];cells=[c for s in file['sheets'] for c in s['cells']]
  self.assertEqual(len(file['sheets']),6);self.assertEqual(len(cells),2269);self.assertEqual(sum(c['value_kind']=='source-error' for c in cells),24);self.assertTrue(validate_graph(self.project))
 def test_cached_formula_and_error_roots_are_preserved(self):
  file=self.project['provenance']['files'][0];cells=[c for s in file['sheets'] for c in s['cells']]
  formulas=[c for c in cells if c['formula']=='1+2'];self.assertEqual(len(formulas),6);self.assertTrue(all(str(c['cached_value']) in ('3','3.0') for c in formulas));self.assertEqual(len(file['dependencies']['error_roots']),24)
 def test_source_draft_retains_every_cell_and_blocks_promotion(self):
  p=source_scope_draft(copy.deepcopy(self.project));self.assertEqual(len([n for n in p['graph']['nodes'] if 'record_kind' in n]),2269);self.assertEqual(p['state'],'draft_incomplete');self.assertFalse(p['modules'])
 def test_graph_and_source_mutation_rejected(self):
  p=copy.deepcopy(self.project);p['graph']['nodes'][0]['source_ids']=['invented'];
  with self.assertRaises(WorkflowError):validate_graph(p)
 def test_atomic_new_save_backup_and_stale_write(self):
  p=copy.deepcopy(self.project);path=self.folder/'draft.amuax';first=save_project(p,path);self.assertEqual(open_project(path)['provenance'],p['provenance']);p['revision']+=1;p['generation_id']=uid()
  with self.assertRaises(WorkflowError):save_project(p,path)
  save_project(p,path,first['sha256']);self.assertTrue(path.with_suffix('.amuax.previous').exists())
 def test_failure_boundaries_retain_valid_generation(self):
  for boundary in ['snapshot','flush','verify','backup','publish','directory-sync']:
   path=self.folder/(boundary+'.amuax');p=copy.deepcopy(self.project);first=save_project(p,path);p['revision']+=1;p['generation_id']=uid()
   with self.assertRaises(OSError):save_project(p,path,first['sha256'],fault=boundary)
   self.assertIn(open_project(path)['revision'],[0,1])
 def test_xml_entities_and_archive_traversal_rejected(self):
  with self.assertRaises(WorkflowError):xml(b'<!DOCTYPE x [<!ENTITY q SYSTEM "file:///etc/passwd">]><x/>')
  data=io.BytesIO()
  with zipfile.ZipFile(data,'w') as z:z.writestr('../outside','x')
  with self.assertRaises(WorkflowError):archive(data.getvalue())
 def test_formula_translation_and_selection_limit(self):
  self.assertEqual(translate_formula('SUM($A1,B$2,"C3")','D4','E5'),'SUM($A2,C$2,"C3")')
  with self.assertRaises(WorkflowError):intake([self.source]*21)
if __name__=='__main__':unittest.main()
