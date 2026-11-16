import sys,json,unittest,tempfile,copy,time,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/provider'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
import model_chat as mc,provider_helper as ph
from broker import BrokerError

EVIDENCE={'scope':'test source','files':[{'name':'fixture.xlsx','sheets':[{'name':'Inputs','cells':[['A1','0.2',None,'literal']]}]}]}
def plan():return {'intent':'build','message':'Explicit synthetic fixture','structure_confirmed_by_user':True,'model':{'name':'Synthetic','dimensions':[{'name':'Cost','symbol':'C'}],'parameters':[{'name':'p','expression':'0.2','sensMin':'0.1','sensMax':'0.3'}],'nodes':[{'id':'root','parent':None,'type':'decision','name':'Choice'},{'id':'a','parent':'root','type':'chance','name':'Treatment'},{'id':'yes','parent':'a','type':'terminal','name':'Event','probability':'p','payoff':['100'],'sources':['fixture.xlsx#Inputs!A1']},{'id':'no','parent':'a','type':'terminal','name':'No event','probability':'1-p','payoff':['10']}]},'questions':[]}
class ChatTests(unittest.TestCase):
 def test_original_xml_and_state_roundtrip(self):
  p=mc.validate(plan(),EVIDENCE);xml=mc.xml_for(p,EVIDENCE);r=ET.fromstring(xml)
  self.assertEqual(r.findtext('type'),'0');self.assertEqual(len(r.findall('tree/Node')),4);self.assertNotIn('AMUA_PENDING_REVIEW',xml)
  current=mc.native_model(xml);self.assertEqual(current['nodes'][2]['probability'],'p');self.assertEqual(mc.saved_state(xml)['evidence'],EVIDENCE)
 def test_missing_values_preserved_and_targeted_answers(self):
  p=plan();p['model']['nodes'][2]['probability']=None;p=mc.validate(p,EVIDENCE)
  self.assertEqual(len(p['questions']),1);self.assertTrue(p['model']['nodes'][2]['probability'].startswith('UNRESOLVED_'))
  xml=mc.xml_for(p,EVIDENCE);e=mc.context(None,{'xml':xml,'sha256':'test'})
  q=p['questions'][0];answer=mc.local_answer(q['id']+' = 0.25',e)
  self.assertEqual(answer['model']['nodes'][2]['probability'],'0.25');self.assertFalse(answer['questions']);self.assertNotIn('AMUA_PENDING_REVIEW',mc.xml_for(answer,e))
 def test_structure_pending_blocks_calculations(self):
  p=plan();p.pop('structure_confirmed_by_user');xml=mc.xml_for(p,EVIDENCE)
  self.assertIn('UNRESOLVED_SCIENTIFIC_INPUTS',xml);e=mc.context(None,{'xml':xml,'sha256':'x'})
  answer=mc.local_answer('approve structure',e);self.assertFalse(answer['questions'])
 def test_question_targets_survive_native_reordering(self):
  p=plan();p['model']['nodes'][2]['probability']=None;xml=mc.xml_for(p,EVIDENCE);root=ET.fromstring(xml);tree=root.find('tree');nodes=list(tree)
  tree.remove(nodes[2]);tree.append(nodes[2]);children=tree.findall('Node')[1].findall('childIndices');children[0].text='3';children[1].text='2'
  e=mc.context(None,{'xml':ET.tostring(root,encoding='unicode'),'sha256':'x'});qid=e['current_model']['questions'][0]['id'];answer=mc.local_answer(qid+' = 0.4',e)
  self.assertEqual(next(n for n in answer['model']['nodes'] if n['name']=='Event')['probability'],'0.4');self.assertEqual(next(n for n in answer['model']['nodes'] if n['name']=='No event')['probability'],'1-p')
 def test_duplicate_native_node_ids_do_not_retarget_questions(self):
  p=plan();p['model']['nodes'][2]['probability']=None;root=ET.fromstring(mc.xml_for(p,EVIDENCE));nodes=root.findall('tree/Node');nodes[3].find('notes').text=nodes[2].findtext('notes')
  current=mc.native_model(ET.tostring(root,encoding='unicode'));self.assertTrue(all(q.get('node')!='yes' for q in current['questions']));self.assertTrue(any(q.get('field')=='structure' for q in current['questions']))
 def test_expression_injection_rejected(self):
  for bad in ['Java.type("java.lang.Runtime")','System.exit(0)','1;2','__import__(x)','Infinity']:
   with self.assertRaises(BrokerError):mc.expression(bad)
 def test_graph_cycle_disconnected_duplicate_invalid_rejected(self):
  for kind in range(4):
   p=plan()
   if kind==0:p['model']['nodes'][1]['parent']='yes'
   if kind==1:p['model']['nodes'][1]['parent']=None
   if kind==2:p['model']['nodes'][1]['id']='root'
   if kind==3:p['model']['nodes'][1]['type']='terminal'
   with self.assertRaises(BrokerError):mc.validate(p,EVIDENCE)
 def test_fabricated_source_rejected(self):
  p=plan();p['model']['nodes'][2]['sources']=['unknown.xlsx#Wrong!A1']
  with self.assertRaises(BrokerError):mc.validate(p,EVIDENCE)
 def test_edit_preserves_native_settings_variables_tables(self):
  p=plan();xml=mc.xml_for(p,EVIDENCE);r=ET.fromstring(xml);r.find('cohortSize').text='587';r.find('crnSeed').text='888';ET.SubElement(r,'Variable').text='preserved-marker';r.find('DimInfo/analysisType').text='2'
  e=mc.context(None,{'xml':ET.tostring(r,encoding='unicode'),'sha256':'x'});q=plan();q['intent']='edit';q['model']['name']='Changed'
  out=ET.fromstring(mc.xml_for(q,e));self.assertEqual(out.findtext('cohortSize'),'587');self.assertEqual(out.findtext('crnSeed'),'888');self.assertEqual(out.findtext('Variable'),'preserved-marker');self.assertEqual(out.findtext('DimInfo/analysisType'),'2')
 def test_question_parameter_resolves(self):
  p=plan();p['model']['parameters'][0]['expression']=None;xml=mc.xml_for(p,EVIDENCE);e=mc.context(None,{'xml':xml,'sha256':'x'})
  answer=mc.local_answer('QP_p = 0.4',e);self.assertEqual(answer['model']['parameters'][0]['expression'],'0.4')
 def test_compact_ckd_all_cells_one_context(self):
  from workflow.core import intake
  path=Path(__file__).resolve().parents[2]/'evidence/inputs/CKD Decision Tree WITH SENSITIVITY ANALYSIS.xlsx'
  if not path.exists():self.skipTest('Private acceptance workbook not present')
  started=time.monotonic();project=intake([str(path)]);e=mc.context(project)
  original=sum(c.get('cached_value') is not None or bool(c.get('effective_formula') or c.get('formula')) for f in project['provenance']['files'] for s in f['sheets'] for c in s['cells'])
  self.assertEqual(sum(len(s['cells']) for f in e['files'] for s in f['sheets']),original);self.assertLess(len(mc.packed(e).encode()),450000)
  draft=mc.initial(e);self.assertGreater(len(draft['model']['nodes']),50);self.assertLess(time.monotonic()-started,5);self.assertTrue(draft['questions'])
 def test_actual_dispatch_one_remote_call_no_chunk_loop(self):
  class Broker:
   def recipient(self):return {'registration':'synthetic-account','epoch':1,'subject':'synthetic','label':'Synthetic','email':'synthetic@example.invalid'}
   def __init__(self):self.support=Path(tempfile.mkdtemp());self.keychain=type('K',(),{'close':lambda self:None})()
   def models(self):return [{'slug':'fixture-model'}]
   def request(self,model,items,instructions,emit,**kwargs):
    self.calls+=1;self.payload=items;sample=plan();sample['model']['nodes'][2]['sources']=[];emit({'event':'delta','text':json.dumps(sample)});return {'completed':True}
   calls=0
  b=Broker();command={'action':'chat-preview','text':'Create a synthetic tree','budget_session_id':'synthetic_session','paths':[]}
  with patch.object(ph,'Broker',return_value=b):
   preview=ph.run(command);command.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_recipient=preview['recipient'],approved_model=preview['resolved_model'],approved_max_calls=1)
   result=ph.run(command)
  self.assertTrue(result['ok']);self.assertEqual(b.calls,1);self.assertIn('<tree>',result['candidate_xml'])
 def test_full_helper_allows_long_valid_proposal(self):
  clock=[0.0];events=[]
  class Broker:
   def recipient(self):return {'registration':'synthetic-account','epoch':1,'subject':'synthetic','label':'Synthetic','email':'synthetic@example.invalid'}
   def __init__(self):self.support=Path(tempfile.mkdtemp());self.keychain=type('K',(),{'close':lambda self:None})()
   def models(self):return [{'slug':'fixture-model'}]
   def request(self,model,items,instructions,emit,**kwargs):
    self.asserted_timeout=kwargs['idle_timeout'];sample=plan();sample['model']['nodes'][2]['sources']=[];text=json.dumps(sample);step=max(1,len(text)//12)
    for index in range(0,len(text),step):clock[0]+=60;emit({'event':'delta','text':text[index:index+step]})
    return {'completed':True}
  b=Broker();cmd={'action':'chat-preview','text':'Create a synthetic tree','budget_session_id':'synthetic_long_session','paths':[],'idle_timeout_seconds':300}
  with patch.object(ph,'Broker',return_value=b),patch('time.monotonic',side_effect=lambda:clock[0]):
   preview=ph.run(cmd);cmd.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_recipient=preview['recipient'],approved_model=preview['resolved_model'],approved_max_calls=1);out=ph.run(cmd,events.append)
  self.assertTrue(out['candidate_xml']);self.assertGreater(out['elapsed_seconds'],110);self.assertEqual(b.asserted_timeout,300);self.assertTrue(all(e['meaningful'] and e['progress_sequence']>0 for e in events));self.assertEqual(out['model'],'fixture-model')
 def test_local_run_no_remote_call(self):
  class Broker:
   def recipient(self):return {'registration':'synthetic-account','epoch':1,'subject':'synthetic','label':'Synthetic','email':'synthetic@example.invalid'}
   def __init__(self):self.keychain=type('K',(),{'close':lambda self:None})()
  b=Broker();cmd={'action':'chat-preview','text':'run model','paths':[]}
  with patch.object(ph,'Broker',return_value=b):
   preview=ph.run(cmd);self.assertEqual(preview['required_calls'],0);cmd.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_max_calls=0);out=ph.run(cmd)
  self.assertEqual(out['proposal']['intent'],'run')
if __name__=='__main__':unittest.main()
