import copy,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src')]
import model_chat as mc,provider_helper as ph
from broker import BrokerError,Broker
from hardening import provider_plan
from workflow.core import WorkflowError,xml,synthetic_project,save_project,open_project,MAX_PROJECT_BYTES
from test_model_chat import plan,EVIDENCE

class FakeBroker:
    def __init__(self,path,account='A'):
        self.support=path;self.account=account;self.calls=[]
        self.keychain=type('K',(),{'close':lambda self:None})()
    def recipient(self):return {'registration':self.account,'epoch':1,'subject':self.account,'label':self.account,'email':'synthetic@example.invalid'}
    def models(self):return [{'slug':'synthetic-model'}]
    def request(self,model,items,instructions,emit,**kwargs):
        self.calls.append(items);emit({'event':'delta','text':json.dumps(plan())});return {'completed':True}

class HardeningTests(unittest.TestCase):
    def test_terminal_cost_rejected_before_candidate(self):
        for cost in ('100','p',None,'1/10'):
            p=plan();p['model']['nodes'][2]['cost']=[cost]
            with self.assertRaisesRegex(BrokerError,'terminal_cost_unsupported'):mc.xml_for(p,EVIDENCE)

    def test_other_engine_ignored_values_rejected(self):
        p=plan();p['model']['nodes'][0]['cost']=['100']
        with self.assertRaisesRegex(BrokerError,'root_cost_unsupported'):mc.xml_for(p,EVIDENCE)
        p=plan();p['model']['nodes'][1]['payoff']=['100']
        with self.assertRaisesRegex(BrokerError,'nonterminal_payoff_unsupported'):mc.xml_for(p,EVIDENCE)
        p=plan();p['model']['simulation']={'cohortSize':1000}
        with self.assertRaisesRegex(BrokerError,'simulation_changes'):provider_plan(p,EVIDENCE)
        p=plan();p['model']['nodes'][1]['probability']='0.5'
        with self.assertRaisesRegex(BrokerError,'ignored_probability'):provider_plan(p,EVIDENCE)

    def test_question_dimension_and_parameter_rejected(self):
        for q in ({'id':'Q1','text':'Payoff','field':'payoff','node':'yes','dimension':999},
                  {'id':'Q1','text':'Cost','field':'cost','node':'yes','dimension':0},
                  {'id':'Q1','text':'Nonterminal payoff','field':'payoff','node':'a','dimension':0},
                  {'id':'Q1','text':'Strategy probability','field':'probability','node':'a'},
                  {'id':'Q1','text':'Parameter','field':'parameter','parameter':'missing'}):
            p=plan();p['questions']=[q]
            with self.assertRaises(BrokerError):mc.validate(p,EVIDENCE)

    def test_provider_cannot_assert_user_source_or_approval(self):
        p=plan();p['model']['parameters'][0]['sources']=['user:invented']
        with self.assertRaisesRegex(BrokerError,'provider_cannot'):provider_plan(p,EVIDENCE)
        checked=provider_plan(plan(),EVIDENCE)
        self.assertNotIn('structure_confirmed_by_user',checked)
        self.assertTrue(any(q['field']=='structure' for q in checked['questions']))

    def test_citation_value_mismatch_requires_separate_review(self):
        p=plan();p['model']['parameters'][0].update(expression='0.95',sources=['fixture.xlsx#Inputs!A1'])
        checked=provider_plan(p,EVIDENCE)
        self.assertTrue(any(i['target']=='p' and i['expression']=='0.95' and '0.2' in i['cited_values'].values() for i in checked['input_review']))
        candidate=mc.xml_for(checked,EVIDENCE)
        evidence=mc.context(None,{'xml':candidate,'sha256':'synthetic'})
        structure=mc.local_answer('approve structure',evidence)
        self.assertTrue(any(q['field']=='input_review' for q in structure['questions']))
        self.assertIn('AMUA_PENDING_REVIEW',mc.xml_for(structure,evidence))
        evidence=mc.context(None,{'xml':mc.xml_for(structure,evidence),'sha256':'synthetic'})
        confirmed=mc.local_answer('approve inputs',evidence)
        self.assertFalse(confirmed['questions'])
        self.assertNotIn('AMUA_PENDING_REVIEW',mc.xml_for(confirmed,evidence))

    def test_literal_match_is_distinguished_from_transformation(self):
        p=plan();p['model']['parameters'][0]['sources']=['fixture.xlsx#Inputs!A1']
        checked=provider_plan(p,EVIDENCE)
        self.assertFalse(any(i['target']=='p' for i in checked.get('input_review',[])))
        p['model']['parameters'][0]['expression']='0.2*100'
        self.assertTrue(any(i['target']=='p' for i in provider_plan(p,EVIDENCE)['input_review']))

    def test_embedded_inventory_requires_opt_in(self):
        private=copy.deepcopy(EVIDENCE);private['files'][0]['sheets'][0]['cells'][0][1]='SYNTHETIC_PRIVATE'
        candidate=mc.xml_for(plan(),private);snapshot={'xml':candidate,'sha256':'synthetic'}
        default=mc.context(None,snapshot)
        self.assertFalse(default['files']);self.assertNotIn('SYNTHETIC_PRIVATE',mc.packed({k:v for k,v in default.items() if k!='base_xml'}))
        self.assertIn('SYNTHETIC_PRIVATE',mc.packed(mc.context(None,snapshot,True)['files']))

    def test_recipient_switch_blocks_before_catalog_and_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            a=FakeBroker(Path(directory),'A');b=FakeBroker(Path(directory),'B')
            command={'action':'chat-preview','text':'Create synthetic model','paths':[],'budget_session_id':'synthetic_hardening'}
            with patch.object(ph,'Broker',return_value=a):preview=ph.run(command)
            command.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_recipient=preview['recipient'],approved_model=preview['resolved_model'],approved_max_calls=1)
            with patch.object(ph,'Broker',return_value=b),patch.object(b,'models',side_effect=AssertionError('No catalog should be sent')):
                with self.assertRaisesRegex(BrokerError,'recipient_changed'):ph.run(command)
            self.assertFalse(b.calls)

    def test_catalog_model_removed_requires_new_review(self):
        with tempfile.TemporaryDirectory() as directory:
            b=FakeBroker(Path(directory));command={'action':'chat-preview','text':'Review synthetic model','paths':[],'budget_session_id':'synthetic_hardening'}
            with patch.object(ph,'Broker',return_value=b):preview=ph.run(command)
            command.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_recipient=preview['recipient'],approved_model='removed-model',approved_max_calls=1)
            with patch.object(ph,'Broker',return_value=b):
                with self.assertRaisesRegex(BrokerError,'model_unavailable'):ph.run(command)
            self.assertFalse(b.calls)

    def test_legacy_request_rejects_unapproved_account(self):
        with tempfile.TemporaryDirectory() as directory:
            b=FakeBroker(Path(directory),'B')
            command={'action':'request','text':'Review','paths':[],'budget_session_id':'synthetic_hardening','approved_max_calls':1,'approved_recipient':{'registration':'A'},'approved_model':'synthetic-model'}
            with patch.object(ph,'Broker',return_value=b),patch.object(b,'models',side_effect=AssertionError('No catalog expected')):
                with self.assertRaisesRegex(BrokerError,'recipient_changed'):ph.run(command)
            self.assertFalse(b.calls)

    def test_utf16_and_utf8_dtds_rejected(self):
        document='<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x "synthetic">]><root>&x;</root>'
        for encoding in ('utf-8','utf-16','utf-16-le','utf-16-be'):
            with self.assertRaisesRegex(WorkflowError,'DTD'):xml(document.encode(encoding))
        self.assertEqual(xml('<root>safe</root>'.encode('utf-16')).text,'safe')

    def test_parser_limits_during_parse(self):
        with self.assertRaises(WorkflowError):xml(('<x>'*103+'</x>'*103).encode())
        with self.assertRaises(WorkflowError):xml(('<x>'+'s'*1000001+'</x>').encode())

    def test_crashed_writer_residue_recovers_live_lock_rejects(self):
        import fcntl
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)/'model.amuax';lock=path.with_suffix('.amuax.lock');lock.write_text('dead writer')
            save_project(synthetic_project(),path)
            self.assertTrue(open_project(path))
            with lock.open('r+') as held:
                fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaisesRegex(WorkflowError,'locked'):save_project(synthetic_project(),path)

    def test_archive_size_checked_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'large.amuax'
            with path.open('wb') as stream:stream.truncate(MAX_PROJECT_BYTES+1)
            with self.assertRaisesRegex(WorkflowError,'12 MiB'):open_project(path)

    def test_stop_reaps_descendant_and_removes_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);helper=directory/'engine_helper.py';helper.write_bytes((ROOT/'src/engine_helper.py').read_bytes())
            runtime=directory/'runtime/bin';runtime.mkdir(parents=True);pidpath=directory/'pid';snapshot=directory/'snapshot'
            stub=runtime/'java';stub.write_text('#!'+sys.executable+'\nimport os,time,sys\nfrom pathlib import Path\nPath('+repr(str(pidpath))+').write_text(str(os.getpid()))\nPath('+repr(str(snapshot))+').write_text(sys.argv[-2])\ntime.sleep(30)\n');stub.chmod(0o700)
            parent=subprocess.Popen([sys.executable,'-B',str(helper)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            childpid=None
            try:
                parent.stdin.write(json.dumps({'action':'engine-analysis','operation':'run','xml':'<synthetic/>','target_hash':'synthetic'}).encode());parent.stdin.close()
                deadline=time.monotonic()+5
                while not snapshot.exists() and time.monotonic()<deadline:time.sleep(.02)
                childpid=int(pidpath.read_text());model=Path(snapshot.read_text())
                parent.terminate();parent.wait(timeout=4)
                with self.assertRaises(ProcessLookupError):os.kill(childpid,0)
                self.assertFalse(model.parent.exists())
            finally:
                if parent.poll() is None:parent.kill();parent.wait()
                if childpid:
                    try:os.kill(childpid,signal.SIGKILL)
                    except ProcessLookupError:pass

    def test_engine_output_budget_stops_oversized_child(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);helper=directory/'engine_helper.py';helper.write_bytes((ROOT/'src/engine_helper.py').read_bytes())
            runtime=directory/'runtime/bin';runtime.mkdir(parents=True);stub=runtime/'java'
            stub.write_text('#!'+sys.executable+'\nimport sys,time\nsys.stdout.buffer.write(b"x"*(9*1024*1024));sys.stdout.buffer.flush();time.sleep(20)\n');stub.chmod(0o700)
            request={'action':'engine-analysis','operation':'run','xml':'<synthetic/>','target_hash':'synthetic'}
            result=subprocess.run([sys.executable,'-B',str(helper)],input=json.dumps(request),capture_output=True,text=True,timeout=5)
            response=json.loads(result.stdout);self.assertFalse(response['ok']);self.assertIn('output limit',response['error']['message'])

if __name__=='__main__':unittest.main()
