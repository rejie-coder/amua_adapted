"""Local proposal boundaries. Provider prose cannot confer user approval."""
import copy
from decimal import Decimal, InvalidOperation
import re
import xml.etree.ElementTree as ET
from broker import BrokerError


def validate_extras(plan):
    model = plan.get('model')
    if model is None:
        return
    if not isinstance(model, dict):
        raise BrokerError('invalid_model_schema')
    if not isinstance(model.get('settings',{}),dict):raise BrokerError('invalid_model_settings')
    if not isinstance(model.get('name','Untitled'),str) or len(model.get('name','Untitled'))>1000:raise BrokerError('invalid_model_name')
    nodes = model.get('nodes', [])
    parameters = model.get('parameters', [])
    dims = model.get('dimensions') or [{'name': 'Outcome', 'symbol': 'O'}]
    if not isinstance(nodes, list) or any(not isinstance(n, dict) for n in nodes):
        raise BrokerError('invalid_model_nodes')
    if not isinstance(parameters, list) or any(not isinstance(p, dict) for p in parameters):
        raise BrokerError('invalid_model_parameters')
    if not isinstance(dims, list) or any(not isinstance(d, dict) for d in dims):
        raise BrokerError('invalid_model_dimensions')
    if len({d.get('symbol') for d in dims if isinstance(d.get('symbol'), str)}) != len(dims):
        raise BrokerError('duplicate_dimension_symbol')
    for node in nodes:
        if not isinstance(node.get('notes', ''), str) or len(node.get('notes', '')) > 32000:
            raise BrokerError('invalid_node_notes')
        # Native terminal nodes expose outcomes through payoff, never cost.
        if node.get('type') == 'terminal':
            costs = node.get('cost')
            if costs is not None and (not isinstance(costs, list) or any(not zero(v) for v in costs)):
                raise BrokerError('terminal_cost_unsupported_use_payoff')
        if node.get('parent') is None and node.get('cost') is not None and (not isinstance(node['cost'],list) or any(not zero(v) for v in node['cost'])):
            raise BrokerError('root_cost_unsupported_use_strategy_node')
        if node.get('type') != 'terminal' and node.get('payoff') is not None and (not isinstance(node['payoff'],list) or any(not zero(v) for v in node['payoff'])):
            raise BrokerError('nonterminal_payoff_unsupported_use_cost_or_terminal')
    byid = {str(n.get('id')): n for n in nodes}
    names = {p.get('name') for p in parameters if isinstance(p.get('name'), str)}
    questions = plan.get('questions', [])
    if not isinstance(questions, list):
        raise BrokerError('invalid_model_questions')
    for q in questions:
        if not isinstance(q, dict) or not isinstance(q.get('text'), str) or len(q['text']) > 32000:
            raise BrokerError('invalid_model_questions')
        field = q.get('field', 'structure')
        if field == 'parameter' and q.get('parameter') not in names:
            raise BrokerError('invalid_question_parameter')
        if field in ('cost', 'payoff', 'probability'):
            node = byid.get(str(q.get('node')))
            if node is None:
                raise BrokerError('invalid_question_target')
            if field == 'cost' and node.get('type') == 'terminal':
                raise BrokerError('terminal_cost_unsupported_use_payoff')
            if field == 'cost' and node.get('parent') is None:raise BrokerError('invalid_question_target')
            if field == 'payoff' and node.get('type') != 'terminal':raise BrokerError('invalid_question_target')
            if field == 'probability' and byid.get(str(node.get('parent')),{}).get('type') != 'chance':raise BrokerError('invalid_question_target')
            if field in ('cost', 'payoff'):
                d = q.get('dimension')
                if type(d) is not int or not 0 <= d < len(dims):
                    raise BrokerError('invalid_question_dimension')


def zero(value):
    try:
        return value is not None and Decimal(str(value).strip()).is_finite() and Decimal(str(value).strip()) == 0
    except InvalidOperation:
        return False


def merge_native(plan, evidence, root):
    """Preserve unrepresented native fields by stable identity, never by position."""
    if plan.get('intent') != 'edit' or not evidence.get('base_xml'):
        return root
    from model_chat import native_model
    original = ET.fromstring(evidence['base_xml'])
    current = native_model(evidence['base_xml'])
    if len(current.get('dimensions',[]))!=len(plan['model']['dimensions']):raise BrokerError('edit_dimension_count_requires_manual_editor')
    old = dict(zip((n['id'] for n in current['nodes']), original.findall('tree/Node')))
    proposed = {n['id']: n for n in plan['model']['nodes']}
    for ident, node in old.items():
        unsupported = [c.tag for c in node if c.tag not in {
            'type', 'name', 'xPos', 'yPos', 'width', 'height', 'parentX', 'parentY',
            'parentType', 'level', 'hasCost', 'hasVarUpdates', 'varUpdates', 'visible',
            'collapsed', 'prob', 'notes', 'cost', 'payoff', 'childIndices'}]
        executable = node.findtext('hasVarUpdates') == 'true' or bool(unsupported)
        if executable and (ident not in proposed or str({'decision': 0, 'chance': 1, 'terminal': 2}[proposed[ident]['type']]) != node.findtext('type')):
            raise BrokerError('edit_would_discard_native_behavior_use_manual_editor')
    for candidate, description in zip(root.findall('tree/Node'), plan['model']['nodes']):
        source = old.get(description['id'])
        if source is None:
            continue
        controlled = {c.tag for c in candidate} - {'hasVarUpdates', 'varUpdates', 'visible', 'collapsed', 'hasCost'}
        preserved = copy.deepcopy(source)
        for tag in controlled:
            for c in list(preserved.findall(tag)):
                preserved.remove(c)
            for c in candidate.findall(tag):
                preserved.append(copy.deepcopy(c))
        # Cost visibility can only change when the cost expression itself changes.
        if [c.text or '0' for c in source.findall('cost')] != description['cost']:
            flag = preserved.find('hasCost')
            if flag is None: flag = ET.SubElement(preserved, 'hasCost')
            flag.text = 'true' if any(not zero(v) for v in description['cost']) else 'false'
        tree = root.find('tree')
        index = list(tree).index(candidate)
        tree.remove(candidate)
        tree.insert(index, preserved)
    return root


def provider_plan(plan, evidence):
    """Require explicit user review of unsupported new scientific expressions."""
    from model_chat import validate, digest
    if not isinstance(plan, dict):
        raise BrokerError('invalid_model_proposal')
    from proposal_contract import normalize_questions
    plan = normalize_questions(plan)
    for key in ('structure_confirmed_by_user', 'input_reviewed_by_user', 'input_review', 'input_review_hash','draft_stage'):
        plan.pop(key, None)
    if not isinstance(plan.get('questions',[]),list):raise BrokerError('invalid_model_questions')
    if any(isinstance(q,dict) and q.get('field')=='input_review' for q in plan.get('questions',[]) if isinstance(plan.get('questions'),list)):raise BrokerError('reserved_question_field')
    model = plan.get('model')
    if not isinstance(model, dict):
        return validate(plan, evidence)
    current = evidence.get('current_model', {})
    if 'native_objects' in model and model['native_objects']!=current.get('native_objects',{}):raise BrokerError('native_objects_require_manual_editor')
    if 'simulation' in model:
        existing=current.get('simulation',{'simType':0,'cohortSize':1,'CRN':True,'crnSeed':1234,'numThreads':1})
        if not isinstance(model['simulation'],dict) or any(str(value).lower()!=str(existing.get(key)).lower() for key,value in model['simulation'].items()):raise BrokerError('simulation_changes_require_manual_editor')
    old_nodes = {n['id']: n for n in current.get('nodes', [])}
    old_params = {p['name']: p for p in current.get('parameters', [])}
    from model_chat import references
    allowed_references=references(evidence)
    existing_unreviewed = any(q.get('field') == 'input_review' for q in current.get('questions', []))
    for kind, rows, oldmap, key in (('node', model.get('nodes', []), old_nodes, 'id'), ('parameter', model.get('parameters', []), old_params, 'name')):
        if not isinstance(rows, list): raise BrokerError('invalid_model_schema')
        for item in rows:
            if not isinstance(item, dict): raise BrokerError('invalid_model_schema')
            old = oldmap.get(str(item.get(key)), {})
            if kind=='node' and any(field in item and item[field]!=old.get(field) for field in ('hasVarUpdates','varUpdates')):raise BrokerError('native_updates_require_manual_editor')
            sources = item.get('sources', [])
            if not isinstance(sources, list): raise BrokerError('invalid_model_source_reference')
            for source in sources:
                if not isinstance(source, str): raise BrokerError('invalid_model_source_reference')
                if not source.startswith('user:') and source not in allowed_references and source not in old.get('sources',[]):raise BrokerError('invalid_model_source_reference')
                if source.startswith('user:') and (source not in old.get('sources', []) or any(item.get(f) != old.get(f) for f in (('expression',) if kind == 'parameter' else ('probability', 'cost', 'payoff')))):
                    raise BrokerError('provider_cannot_assert_user_source')
    plan = validate(plan, evidence)
    proposed_nodes={n['id']:n for n in plan['model']['nodes']}
    for n in plan['model']['nodes']:
        if proposed_nodes.get(n['parent'],{}).get('type')!='chance' and n.get('probability') is not None and not zero(n['probability']):raise BrokerError('ignored_probability_requires_chance_parent')
    values = {}
    for f in evidence.get('files', []):
        for sheet in f.get('sheets', []):
            for cell in sheet.get('cells', []):
                values[f['name'] + '#' + sheet['name'] + '!' + cell[0]] = cell[1]
    issues = []
    def inspect(target, field, value, sources, previous=None, dimension=None):
        if value is None or str(value).startswith('UNRESOLVED_'): return
        if previous == value and not existing_unreviewed: return
        cited = {s: values[s] for s in sources if s in values}
        try:
            number = Decimal(value)
            literal_match = number.is_finite() and any(Decimal(str(v)) == number for v in cited.values())
        except (InvalidOperation, ValueError, TypeError):
            literal_match = False
        if literal_match: return
        issues.append({'target': target, 'field': field, 'dimension': dimension, 'expression': value,
                       'cited_values': cited, 'sources': sources,
                       'status': 'unverified expression or transformation; confirm value, units and basis'})
    for p in plan['model']['parameters']:
        inspect(p['name'], 'parameter', p['expression'], p.get('sources', []), old_params.get(p['name'], {}).get('expression'))
    parents = {n['id']: n for n in plan['model']['nodes']}
    for n in plan['model']['nodes']:
        old = old_nodes.get(n['id'], {})
        if parents.get(n['parent'], {}).get('type') == 'chance':
            inspect(n['id'], 'probability', n['probability'], n.get('sources', []), old.get('probability'))
        for field in ('cost', 'payoff'):
            if field == 'payoff' and n['type'] != 'terminal': continue
            if field == 'cost' and n['type'] == 'terminal': continue
            for d, v in enumerate(n[field]):
                if field == 'cost' and zero(v): continue
                previous = old.get(field, [])
                inspect(n['id'], field, v, n.get('sources', []), previous[d] if d < len(previous) else None, d)
    if issues:
        plan['questions'] = [q for q in plan['questions'] if q.get('field') != 'input_review']
        plan['questions'].append({'id': 'Q_INPUT_REVIEW', 'field': 'input_review',
            'text': str(len(issues)) + ' scientific expressions need review. Open Review proposed inputs, check values, units and derivations, then explicitly confirm. Approving structure does not approve these inputs.'})
        plan['input_review'] = issues
        plan['input_review_hash'] = digest(issues)
    plan['draft_stage']='model_proposal'
    return validate(plan, evidence)
