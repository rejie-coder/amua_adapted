"""Real image preparation and provider dispatch; synthetic remote response only."""
import base64,copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src')]
import provider_helper as ph,model_chat as mc
from workflow_helper import dispatch
from broker import BrokerError
FIXTURES=Path(__file__).parent/'fixtures'

class ImageBroker:
    def __init__(self,support):
        self.support=Path(support);self.calls=[];self.keychain=type('K',(),{'close':lambda self:None})()
    def recipient(self):return {'registration':'synthetic-image-account','epoch':1,'subject':'synthetic','label':'Synthetic image test','email':'test@example.invalid'}
    def models(self):return [{'slug':'synthetic-image-model'}]
    def request(self,model,items,instructions,emit,**kwargs):
        images=[part['image_url'] for message in items for part in message.get('content',[]) if isinstance(part,dict) and part.get('type')=='input_image']
        assert len(images)==1
        assert base64.b64decode(images[0].split(',',1)[1])==(FIXTURES/'drug-table.png').read_bytes()
        assert 'Native model contract' in instructions
        assert 'costs for a terminal' in instructions.lower() or 'terminal outcome belong in payoff' in instructions
        assert not any('<Model>' in str(message) for message in items),'Known MCP model must not be supplied as evidence'
        self.calls.append({'model':model,'image_sha256':hashlib.sha256(base64.b64decode(images[0].split(',',1)[1])).hexdigest()})
        raw=json.loads((FIXTURES/'drug-table-proposal-with-unbound-questions.json').read_text())
        emit({'event':'delta','text':json.dumps(raw)});return {'completed':True}


def image_chat(support):
    image=FIXTURES/'drug-table.png';project=dispatch({'action':'intake','paths':[str(image)]})['project']
    broker=ImageBroker(support)
    request={'action':'chat-preview','text':'Can we create a decision tree for this data set?','paths':[str(image)],'project':project,'make_outline':True,'budget_session_id':'synthetic_image_chat'}
    with patch.object(ph,'Broker',return_value=broker):
        preview=ph.run(request)
        request.update(action='chat-request',approved_context_hash=preview['context_hash'],approved_recipient=preview['recipient'],approved_model=preview['resolved_model'],approved_max_calls=1)
        response=ph.run(request)
    return preview,response,broker

class ImageChatTests(unittest.TestCase):
    def test_real_image_dispatch_keeps_numeric_tree_with_context_questions(self):
        with tempfile.TemporaryDirectory() as support:preview,response,broker=image_chat(support)
        self.assertEqual(len(broker.calls),1)
        self.assertIn('images are supplied as image inputs',mc.context()['scope'])
        self.assertEqual(preview['outgoing_manifest']['images'],[str(FIXTURES/'drug-table.png')])
        self.assertEqual(mc.saved_state(preview['draft_xml'])['proposal']['draft_stage'],'source_outline')
        self.assertEqual(response['proposal_stage'],'model_proposal')
        self.assertEqual(len(response['proposal']['model']['nodes']),7)
        self.assertEqual(len(response['proposal']['model']['dimensions']),2)
        self.assertIn('AMUA_PENDING_REVIEW',response['candidate_xml'])
        self.assertEqual(len(response['proposal']['question_binding_warnings']),3)
        self.assertTrue(any(q['field']=='input_review' for q in response['proposal']['questions']))
        self.assertTrue(any(q['id']=='Q_WTP' and q['field']=='structure' for q in response['proposal']['questions']))
        values={p['name']:p['expression'] for p in response['proposal']['model']['parameters']}
        self.assertEqual(values['cost_A_success'],'1000');self.assertEqual(values['qaly_B_failure'],'1.0')

    def test_structure_review_cannot_clear_image_input_review(self):
        with tempfile.TemporaryDirectory() as support:_,response,_=image_chat(support)
        evidence=mc.context(None,{'xml':response['candidate_xml'],'sha256':'synthetic'})
        answer=mc.local_answer('approve structure',evidence)
        self.assertTrue(any(q['field']=='input_review' for q in answer['questions']))
        self.assertIn('AMUA_PENDING_REVIEW',mc.xml_for(answer,evidence))

if __name__=='__main__':unittest.main()
