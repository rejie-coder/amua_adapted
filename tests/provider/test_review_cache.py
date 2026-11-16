import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src/provider')]
import provider_helper
import review_cache
from broker import Broker,BrokerError
from chunks import partition
from transport import prepare_transport
from review_cache import ReviewCache,binding_for
from test_provider import MemoryKeys
class ReviewCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()));self.b=Broker(self.temp.name,MemoryKeys())
        self.project={'provenance':{'files':[{'id':'source','records':[{'id':'record'+str(i),'text':'sourcefact '*2500} for i in range(12)]}]}}
        self.transport,self.meta=prepare_transport(self.project);self.chunks,self.ledger=partition(self.transport,self.meta['source_ids'])
        self.command={'action':'request','text':'PRIVATE_QUESTION_NOT_TO_STORE','history':[{'role':'user','content':'PRIVATE_HISTORY_NOT_TO_STORE'}],'project':self.project,'model':'from-account','budget_session_id':'synthetic-session-uuid','approved_max_calls':len(self.chunks),'approved_transport_hash':self.meta['transport_hash']}
        self.command.update(approved_recipient=self.b.recipient(),approved_model='from-account')
        self.binding=binding_for(self.command,self.meta,'from-account',self.b)
    def tearDown(self):self.temp.cleanup()
    def cache(self):return ReviewCache(self.b.support,self.binding,self.chunks,copy.deepcopy(self.ledger))
    def fake_request(self,calls,fail_at=None):
        def request(model,items,instructions,emit):
            chunk=json.loads(items[-1]['content'][0]['text'].removeprefix('Untrusted project chunk '));calls.append(chunk['chunk_id'])
            if fail_at is not None and len(calls)==fail_at:raise BrokerError('network_or_protocol_error')
            emit({'event':'delta','text':json.dumps({'chunk_id':chunk['chunk_id'],'record_ids':[r['record_id'] for r in chunk['records']],'analysis':'Source review summary; scientific interpretation remains unresolved.'})})
            return {'completed':True,'model':model,'epoch':0}
        return request
    def test_partial_failure_preview_and_resume_only_pending(self):
        calls=[]
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',return_value=[{'slug':'from-account'}]),patch.object(self.b,'request',side_effect=self.fake_request(calls,2)):
            with self.assertRaises(BrokerError) as caught:provider_helper.run(self.command)
        self.assertEqual(caught.exception.review_progress['completed_chunks'],1)
        preview={**self.command,'action':'preview'}
        with patch.object(provider_helper,'Broker',return_value=self.b):progress=provider_helper.run(preview)
        self.assertEqual(progress['required_calls'],len(self.chunks)-1);self.assertEqual(progress['calls_used'],2);self.assertTrue(progress['resume_available'])
        resumed={**self.command,'approved_max_calls':progress['required_calls'],'approved_review_hash':progress['review_binding_hash']}
        resumed_calls=[]
        with patch.object(provider_helper,'Broker',return_value=self.b),patch.object(self.b,'models',return_value=[{'slug':'from-account'}]),patch.object(self.b,'request',side_effect=self.fake_request(resumed_calls)):result=provider_helper.run(resumed)
        self.assertEqual(resumed_calls,[c['chunk_id'] for c in self.chunks[1:]])
        self.assertEqual(result['completed_chunks'],len(self.chunks));self.assertEqual(result['calls_used'],len(self.chunks)+1);self.assertEqual(result['required_calls'],0);self.assertFalse(result['coverage']['semantic_complete'])
    def test_binding_changes_cannot_reuse_old_review(self):
        cache=self.cache();cache.commit(self.chunks[0],'Source-only checked summary')
        variants=[]
        for field,value in [('question_hash','changed'),('history_hash','changed'),('model','other'),('account_binding','other'),('budget_session_hash','other'),('transport_hash','other')]:
            variants.append({**self.binding,field:value})
        for binding in variants:self.assertEqual(ReviewCache(self.b.support,binding,self.chunks,copy.deepcopy(self.ledger)).progress()['completed_chunks'],0)
    def test_cache_permissions_no_prompt_history_or_credentials(self):
        cache=self.cache();cache.commit(self.chunks[0],'Source-only checked summary')
        data=cache.path.read_text();self.assertNotIn('PRIVATE_QUESTION_NOT_TO_STORE',data);self.assertNotIn('PRIVATE_HISTORY_NOT_TO_STORE',data);self.assertNotIn('access_token',data);self.assertNotIn('refresh_token',data)
        self.assertEqual(cache.path.stat().st_mode & 0o777,0o600)
        a=self.cache();a.acquire();b=self.cache()
        try:
            with self.assertRaisesRegex(BrokerError,'review_in_progress'):b.acquire()
        finally:a.close();b.close()
    def test_corrupt_cache_rejected_not_silently_restarted(self):
        cache=self.cache();cache.commit(self.chunks[0],'Source-only checked summary');data=json.loads(cache.path.read_text());data['accepted'][self.chunks[0]['chunk_id']]['analysis']='tampered';cache.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(BrokerError,'review_checkpoint_invalid'):self.cache()
    def test_atomic_publish_fault_keeps_prior_generation(self):
        cache=self.cache();cache.commit(self.chunks[0],'First source summary');before=cache.path.read_bytes()
        with patch.object(review_cache.os,'replace',side_effect=OSError('synthetic publish failure')):
            with self.assertRaises((OSError,BrokerError)):cache.commit(self.chunks[1],'Second source summary')
        self.assertEqual(cache.path.read_bytes(),before);self.assertEqual(cache.progress()['completed_chunks'],1);self.assertEqual(self.cache().progress()['completed_chunks'],1)
if __name__=='__main__':unittest.main(verbosity=2)
