"""Provider contract and non-executable clarification normalization.

Malformed numerical targets are never guessed or applied. Their questions remain
as explicit unbound clarifications, so the model's review guard stays in place.
"""
import copy,re
from broker import BrokerError

CONTRACT = '''
Native model contract (follow exactly):
1. For a strategy/outcome image table, transcribe each row, then build one root
decision, one chance node per strategy and one terminal per outcome. Do not put
probabilities on strategy alternatives. Read the actual image, including all
column headers, units, decimal points and rows. Never invent an obscured value.
2. Outcome dimensions are independent. For a table with Cost ($) and QALYs use
dimensions [{"name":"Cost ($)","symbol":"C"},{"name":"Effectiveness (QALYs)","symbol":"Q"}].
Prefer short identifiers C and Q for symbols. Native currency labels $, €, £ and ¥ are also supported; symbols are labels, never formulas or parameter names. Costs for a
terminal outcome belong in payoff[0], QALYs in payoff[1]. Its cost is ["0","0"].
Every cost/payoff array must have exactly one entry per dimension. Nonterminal
payoff and root cost must be zero. Do not put money into probabilities or QALYs.
3. Example of layout ONLY (numbers are placeholders, not source evidence):
{"id":"choice","parent":null,"type":"decision","name":"Choose strategy","probability":null,"cost":["0","0"],"payoff":["0","0"]}
{"id":"strategy_one","parent":"choice","type":"chance","name":"source strategy name","probability":null,"cost":["0","0"],"payoff":["0","0"]}
{"id":"outcome_one","parent":"strategy_one","type":"terminal","name":"source outcome name","probability":"source_probability_parameter","cost":["0","0"],"payoff":["source_cost_parameter","source_qaly_parameter"]}
Include all sibling outcomes and strategies and define every named parameter.
4. Image citations use the exact selected image filename. Workbook citations use
filename#sheet!cell. A citation is proposed evidence, not proof. Never invent a
"user:" source. Image-derived inputs will require local user review.
5. Questions about horizon, perspective, currency year, WTP, population basis or
assumptions use {"id":"Q_CONTEXT","field":"structure","text":"precise question"}.
Omit node, dimension and parameter for these whole-model questions. Unknown
context must not prevent creating the supported tree or reading visible values.
6. A targeted numeric question must reference an EXACT existing node ID or
parameter name. Probability targets must be children of chance nodes. Payoff
targets must be terminals, with a zero-based dimension index. Parameter questions
need "parameter":"actual_parameter_name"; do not use node for parameters.
No nodeid/all/model placeholders. Never bind a cost question to a terminal;
use payoff with the Cost dimension. Use null for genuinely missing values.
7. For a new cost/QALY comparison use analysisType=1, costDim=0, effectDim=1,
objectiveDim=1 and baseScenario equal to an EXACT strategy name. Identify an
unconfirmed comparator explicitly. A missing WTP is not a confirmed zero value:
ask a structure question and state that a software default cannot select a drug.
8. Return a complete native proposal and a message stating what was transcribed,
what remains uncertain and that Apply tree proposal is the next step. Never say
the model was applied, validated or run. Those are separate local operations.
'''

def normalize_questions(plan):
    if not isinstance(plan,dict):raise BrokerError('invalid_model_proposal')
    result=copy.deepcopy(plan);model=result.get('model')
    if not isinstance(model,dict):return result
    questions=result.get('questions',[])
    if not isinstance(questions,list) or len(questions)>2000:raise BrokerError('invalid_model_questions')
    nodes=model.get('nodes',[]);parameters=model.get('parameters',[])
    if not isinstance(nodes,list) or not isinstance(parameters,list):raise BrokerError('invalid_model_schema')
    byid={str(n.get('id')):n for n in nodes if isinstance(n,dict)}
    names={p.get('name') for p in parameters if isinstance(p,dict) and isinstance(p.get('name'),str)}
    dims=model.get('dimensions') or [{}];warnings=[];used=set()
    for index,q in enumerate(questions):
        if not isinstance(q,dict) or not isinstance(q.get('text'),str) or len(q['text'])>32000:raise BrokerError('invalid_model_questions')
        field=q.get('field','structure');original={k:q.get(k) for k in ('field','node','parameter','dimension') if k in q}
        ident=q.get('id');renamed=not isinstance(ident,str) or not re.fullmatch(r'Q[A-Za-z0-9_]{1,90}',ident) or ident in used or ident=='Q_INPUT_REVIEW'
        if renamed:
            ident='Q_CLAR_'+str(index+1)
            while ident in used:ident+='x'
            q['id']=ident
        used.add(ident)
        if field=='input_review':raise BrokerError('reserved_question_field')
        if field in ('structure','context','assumption','settings','setting','scope','analysis'):
            q['field']='structure'
            for key in ('node','parameter','dimension'):q.pop(key,None)
            if field!='structure' or any(k in original for k in ('node','parameter','dimension')) or renamed:
                warnings.append({'question':ident,'action':'retained as whole-model clarification','original_target':original})
            continue
        if field not in ('probability','cost','payoff','parameter'):raise BrokerError('invalid_question_field')
        node=byid.get(str(q.get('node')));valid=True
        if field=='parameter':valid=q.get('parameter') in names
        else:
            valid=node is not None
            if valid and field=='probability':valid=byid.get(str(node.get('parent')),{}).get('type')=='chance'
            if valid and field=='cost':valid=node.get('type')!='terminal' and node.get('parent') is not None
            if valid and field=='payoff':valid=node.get('type')=='terminal'
            if valid and field in ('cost','payoff'):valid=type(q.get('dimension')) is int and 0<=q['dimension']<len(dims)
        if valid:
            if field=='parameter':
                for key in ('node','dimension'):q.pop(key,None)
            if renamed:warnings.append({'question':ident,'action':'assigned a unique question ID','original_target':original})
            continue
        # Preserve the request for information, not an executable guessed target.
        q['field']='structure';q['unbound_target']=original
        for key in ('node','parameter','dimension'):q.pop(key,None)
        q['text']='Clarification (no value was assigned to a guessed target): '+str(q.get('text',''))
        warnings.append({'question':ident,'action':'invalid numeric binding retained as unbound clarification','original_target':original})
    if warnings:result['question_binding_warnings']=warnings
    return result


def proposal_error(error):
    category=str(error)
    explanations={
        'invalid_question_target':'A numerical question did not identify an existing supported node.',
        'invalid_question_dimension':'A numerical question used an invalid outcome dimension.',
        'invalid_model_dimensions':'Outcome symbols must be short labels such as C, Q or a supported currency sign; not formulas or executable names.',
        'invalid_model_values':'Every cost and payoff array must have one expression per outcome dimension.',
        'terminal_cost_unsupported_use_payoff':'Terminal costs must be zero. Place terminal cost in the Cost dimension of payoff.',
        'invalid_model_settings':'Analysis settings must identify valid outcome dimensions and a supported analysis type.',
        'invalid_model_source_reference':'Use an exact selected image filename, or an existing workbook cell reference.',
        'ignored_probability_requires_chance_parent':'Only chance branches have probabilities; strategy alternatives are decisions.',
    }
    error.details={'category':category,'message':explanations.get(category,'The proposal failed local checks ('+category+'). No final tree was applied.'),
                   'retry_hint':'Retry requests a corrected proposal with this validation reason, after a fresh account/model review. No automatic retry was started.'}
    return error
