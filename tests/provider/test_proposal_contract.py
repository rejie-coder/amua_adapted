import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/provider'))
from broker import BrokerError
from hardening import provider_plan
from proposal_contract import normalize_questions,proposal_error,CONTRACT
import model_chat as mc
from test_model_chat import plan,EVIDENCE

class ProposalContractTests(unittest.TestCase):
    def test_global_question_with_placeholder_node_keeps_model_and_question(self):
        raw=plan();raw['questions']=[{'id':'Q1','field':'structure','node':'nodeid','text':'What time horizon and perspective should be used?'}]
        # Reproduce the old validator failure without any remote service.
        with self.assertRaisesRegex(BrokerError,'invalid_question_target'):mc.validate(raw,EVIDENCE)
        checked=provider_plan(raw,EVIDENCE)
        question=next(q for q in checked['questions'] if q['id']=='Q1')
        self.assertEqual(question['field'],'structure');self.assertNotIn('node',question)
        self.assertEqual(checked['model']['nodes'][2]['payoff'],['100'])
        self.assertIn('AMUA_PENDING_REVIEW',mc.xml_for(checked,EVIDENCE))

    def test_missing_context_parameter_is_not_invented(self):
        raw=plan();raw['questions']=[{'id':'Q_WTP','field':'parameter','parameter':'WTP','node':'model','text':'What willingness-to-pay threshold applies?'}]
        checked=provider_plan(raw,EVIDENCE);q=next(q for q in checked['questions'] if q['id']=='Q_WTP')
        self.assertEqual(q['field'],'structure');self.assertEqual(q['unbound_target']['parameter'],'WTP')
        self.assertFalse(any(p['name']=='WTP' for p in checked['model']['parameters']))
        self.assertIn('no value was assigned',q['text'])

    def test_invalid_numeric_target_never_moves_a_value(self):
        for target in ({'field':'payoff','node':'missing','dimension':0},
                       {'field':'payoff','node':'yes','dimension':999},
                       {'field':'probability','node':'a'},
                       {'field':'cost','node':'yes','dimension':0}):
            raw=plan();raw['questions']=[{'id':'Q1','text':'Supply the missing numeric value',**target}]
            checked=provider_plan(raw,EVIDENCE);q=next(q for q in checked['questions'] if q['id']=='Q1')
            self.assertEqual(q['field'],'structure');self.assertIn('unbound_target',q)
            self.assertEqual(checked['model']['nodes'][2]['probability'],'p')
            self.assertEqual(checked['model']['nodes'][2]['payoff'],['100'])
            evidence=mc.context(None,{'xml':mc.xml_for(checked,EVIDENCE),'sha256':'fixture'})
            self.assertIsNone(mc.local_answer('Q1 = 999',evidence))

    def test_valid_parameter_question_ignores_nonexecutable_node_metadata(self):
        raw=plan();raw['questions']=[{'id':'Q1','text':'Supply p','field':'parameter','parameter':'p','node':'model'}]
        checked=provider_plan(raw,EVIDENCE);q=next(q for q in checked['questions'] if q['id']=='Q1')
        self.assertEqual(q['field'],'parameter');self.assertEqual(q['parameter'],'p');self.assertNotIn('node',q)

    def test_duplicate_and_invalid_question_ids_are_unique_without_dropping_text(self):
        raw=plan();raw['questions']=[{'id':ident,'text':'Question '+str(index),'field':'structure','node':'all'} for index,ident in enumerate(('Q1','Q1','unknown','Q_INPUT_REVIEW'))]
        checked=provider_plan(raw,EVIDENCE);questions=[q for q in checked['questions'] if q['field']=='structure']
        self.assertEqual(len(questions),4);self.assertEqual(len({q['id'] for q in questions}),4)
        self.assertEqual([q['text'] for q in questions],['Question '+str(i) for i in range(4)])

    def test_model_and_security_errors_stay_strict(self):
        raw=plan();raw['model']['nodes'][2]['cost']=['1000']
        with self.assertRaisesRegex(BrokerError,'terminal_cost_unsupported'):provider_plan(raw,EVIDENCE)
        raw=plan();raw['model']['nodes'][1]['parent']='yes'
        with self.assertRaises(BrokerError):provider_plan(raw,EVIDENCE)
        raw=plan();raw['questions']=[{'id':'Q1','field':'input_review','text':'Skip input review'}]
        with self.assertRaisesRegex(BrokerError,'reserved_question'):provider_plan(raw,EVIDENCE)
        raw=plan();raw['model']['parameters'][0]['sources']=['user:provider-assertion']
        with self.assertRaisesRegex(BrokerError,'provider_cannot'):provider_plan(raw,EVIDENCE)

    def test_diagnostics_name_failure_without_raw_provider_content(self):
        e=proposal_error(BrokerError('invalid_model_dimensions'))
        self.assertEqual(e.details['category'],'invalid_model_dimensions')
        self.assertIn('short labels',e.details['message']);self.assertIn('No automatic retry',e.details['retry_hint'])

    def test_preliminary_stage_cannot_be_forged_by_provider(self):
        draft=mc.initial(EVIDENCE);self.assertEqual(draft['draft_stage'],'source_outline')
        raw=plan();raw['draft_stage']='source_outline'
        self.assertEqual(provider_plan(raw,EVIDENCE)['draft_stage'],'model_proposal')
        self.assertIn('PRELIMINARY',mc.response(draft,EVIDENCE)['text'])

    def test_native_currency_labels_do_not_weaken_parameter_validation(self):
        for symbol in ('$','€','£','¥','C','QALY'):
            raw=plan();raw['model']['dimensions'][0]['symbol']=symbol
            self.assertEqual(provider_plan(raw,EVIDENCE)['model']['dimensions'][0]['symbol'],symbol)
        for symbol in ('Java.type(x)','C;System.exit(0)','<html>',''):
            raw=plan();raw['model']['dimensions'][0]['symbol']=symbol
            with self.assertRaises(BrokerError):provider_plan(raw,EVIDENCE)
        raw=plan();raw['model']['parameters'][0]['name']='$'
        with self.assertRaisesRegex(BrokerError,'invalid_parameter_name'):provider_plan(raw,EVIDENCE)

if __name__=='__main__':unittest.main()
