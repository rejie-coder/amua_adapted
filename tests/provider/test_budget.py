import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src/provider'))
import provider_helper
from broker import Broker,BrokerError
from transport import prepare_transport
from budget import operate
from test_provider import MemoryKeys
class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()));self.b=Broker(self.temp.name,MemoryKeys());self.session='synthetic-session-uuid'
    def tearDown(self):self.temp.cleanup()
    def test_usage_counter_exceeds_old_cap_and_persists(self):
        for i in range(75):self.assertEqual(operate(self.b.support,self.session,True)['calls_used'],i+1)
        state=operate(self.b.support,self.session)
        self.assertEqual(state['calls_used'],75);self.assertIsNone(state['remaining_calls']);self.assertIsNone(state['session_call_limit']);self.assertFalse(state['session_limit_enforced'])
        for i in range(130):operate(self.b.support,'synthetic-session-'+str(i),True)
        self.assertEqual(operate(self.b.support,self.session)['calls_used'],75)

    def test_full_source_request_over32_after_prior_usage_completes(self):
        from chunks import partition
        project={'provenance':{'files':[{'id':'source','records':[{'id':'r'+str(i),'text':'synthetic-fact '*6000} for i in range(65)]}]}}
        transport,meta=prepare_transport(project);chunks,ledger=partition(transport,meta['source_ids'])
        self.assertGreater(len(chunks),32)
        for i in range(45):operate(self.b.support,self.session,True)
        def request(model,items,instructions,emit):
            chunk=json.loads(items[-1]['content'][0]['text'].removeprefix('Untrusted project chunk '))
            emit({'event':'delta','text':json.dumps({'chunk_id':chunk['chunk_id'],'record_ids':[r['record_id'] for r in chunk['records']],'analysis':'Synthetic source summary'})})
            return {'completed':True,'model':model,'epoch':0}
        command={'action':'request','text':'test','budget_session_id':self.session,'approved_max_calls':len(chunks),'project':project,'approved_transport_hash':meta['transport_hash']}
        command.update(approved_recipient=self.b.recipient(),approved_model='from-account')
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',return_value=[{'slug':'from-account'}]),patch.object(self.b,'request',side_effect=request) as calls:
            result=provider_helper.run(command)
        self.assertEqual(calls.call_count,len(chunks));self.assertEqual(result['calls_used'],45+len(chunks));self.assertIsNone(result['session_call_limit']);self.assertEqual(result['required_calls'],0)

    def test_preview_is_offline_and_exact(self):
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',side_effect=AssertionError('network forbidden')):
            reply=provider_helper.run({'action':'preview','text':'test','budget_session_id':self.session,'project':{'provenance':{'files':[{'id':'one'}]}}})
        self.assertEqual(reply['required_calls'],1);self.assertEqual(reply['source_id_count'],1);self.assertEqual(reply['calls_used'],0);self.assertFalse(reply['connected'])
    def test_missing_approval_prevents_network(self):
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',side_effect=AssertionError('network forbidden')):
            with self.assertRaisesRegex(BrokerError,'approval_required'):provider_helper.run({'action':'request','text':'test','budget_session_id':self.session})
    def test_all_chunks_ack_and_counted(self):
        project={'provenance':{'files':[{'id':'source','records':[{'id':str(i),'text':'private source '*1000} for i in range(30)]}]}}
        def request(model,items,instructions,emit):
            chunk=json.loads(items[-1]['content'][0]['text'].removeprefix('Untrusted project chunk '))
            emit({'event':'delta','text':json.dumps({'chunk_id':chunk['chunk_id'],'record_ids':[r['record_id'] for r in chunk['records']],'analysis':'unresolved'})})
            return {'completed':True,'model':model,'epoch':0}
        command={'action':'request','text':'test','budget_session_id':self.session,'approved_max_calls':32,'project':project,'approved_transport_hash':prepare_transport(project)[1]['transport_hash']}
        command.update(approved_recipient=self.b.recipient(),approved_model='from-account')
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',return_value=[{'slug':'from-account'}]),patch.object(self.b,'request',side_effect=request):reply=provider_helper.run(command)
        ledger=reply['coverage'];self.assertEqual(reply['calls_used'],ledger['chunk_count']);self.assertEqual(ledger['status'],'all_transport_acknowledged');self.assertFalse(ledger['semantic_complete'])
        saved=list((self.b.support/'coverage-ledgers').iterdir())[0].read_text();self.assertNotIn('private source',saved)
    def test_opted_progress_events_metadata_only(self):
        project={'provenance':{'files':[{'id':'source','records':[{'id':'record','text':'PRIVATE SOURCE CONTENT'}]}]}}
        def request(model,items,instructions,emit):
            chunk=json.loads(items[-1]['content'][0]['text'].removeprefix('Untrusted project chunk '))
            emit({'event':'delta','text':json.dumps({'chunk_id':chunk['chunk_id'],'record_ids':[r['record_id'] for r in chunk['records']],'analysis':'Unresolved source review'})})
            return {'completed':True,'model':model,'epoch':0}
        command={'action':'request','text':'PRIVATE QUESTION','budget_session_id':self.session,'approved_max_calls':1,'project':project,'approved_transport_hash':prepare_transport(project)[1]['transport_hash']}
        command.update(approved_recipient=self.b.recipient(),approved_model='from-account')
        events=[]
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',return_value=[{'slug':'from-account'}]),patch.object(self.b,'request',side_effect=request):provider_helper.run(command,events.append)
        self.assertTrue(events);self.assertEqual(events[-1]['completed_chunks'],1)
        for event in events:self.assertEqual(set(event),{'event','completed_chunks','total_chunks','state'});self.assertNotIn('PRIVATE',json.dumps(event))
    def test_failed_turn_consumes_budget_and_persists_incomplete(self):
        command={'action':'request','text':'test','budget_session_id':self.session,'approved_max_calls':1,'project':{'provenance':{'files':[{'id':'one'}]}}}
        command.update(approved_recipient=self.b.recipient(),approved_model='from-account')
        command['approved_transport_hash']=prepare_transport(command['project'])[1]['transport_hash']
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',return_value=[{'slug':'from-account'}]),patch.object(self.b,'request',side_effect=BrokerError('http_429')):
            with self.assertRaisesRegex(BrokerError,'http_429'):provider_helper.run(command)
        self.assertEqual(operate(self.b.support,self.session)['calls_used'],1)
        ledger=json.loads(next((self.b.support/'coverage-ledgers').iterdir()).read_text());self.assertEqual(ledger['status'],'incomplete');self.assertFalse(ledger['semantic_complete'])
if __name__=='__main__':unittest.main(verbosity=2)
