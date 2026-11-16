"""Lossless bounded project partitioning; acknowledgements never prove semantics."""
import hashlib
import json
from broker import BrokerError
MAX_PROJECT=32*1024*1024
RECORD_BYTES=48*1024
CHUNK_BYTES=128*1024

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def sha(value):return hashlib.sha256(canonical(value)).hexdigest()
def nested_ids(value):
    result=[]
    if isinstance(value,dict):
        if isinstance(value.get('id'),str):result.append(value['id'])
        for child in value.values():result.extend(nested_ids(child))
    elif isinstance(value,list):
        for child in value:result.extend(nested_ids(child))
    return result

def partition(project, source_ids=None):
    if len(canonical(project))>MAX_PROJECT:raise BrokerError('project_limit_32mib')
    source_root=project.get('provenance',{}).get('files',[]) if isinstance(project,dict) else project
    declared_ids=set(nested_ids(source_root)) if source_ids is None else set(source_ids)
    def record_sources(value):
        if source_ids is None:return set(nested_ids(value))
        if isinstance(value,str):return {value} & declared_ids
        if isinstance(value,dict):return set().union(*(record_sources(v) for v in value.values())) if value else set()
        if isinstance(value,list):return set().union(*(record_sources(v) for v in value)) if value else set()
        return set()
    records=[]
    def walk(value,path):
        encoded=canonical(value)
        if len(encoded)<=RECORD_BYTES:
            record={'path':path,'value':value};record['record_id']=sha(record);record['source_ids']=sorted((record_sources(value) | ({value} if path and path[-1]=='id' and isinstance(value,str) else set())) & declared_ids);records.append(record);return
        if isinstance(value,dict):
            for key in sorted(value):walk(value[key],path+[key])
        elif isinstance(value,list):
            for i,child in enumerate(value):walk(child,path+[i])
        elif isinstance(value,str):
            # Unicode character slices are kept whole; exact ordered fragments recover original.
            size=RECORD_BYTES//8
            for i in range(0,len(value),size):
                record={'path':path,'fragment_index':i//size,'fragment_count':(len(value)+size-1)//size,'value':value[i:i+size]};record['record_id']=sha(record);record['source_ids']=[];records.append(record)
        else:raise BrokerError('project_record_limit')
    walk(project,[])
    chunks=[];group=[];size=0
    for record in records:
        weight=len(canonical({k:v for k,v in record.items() if k!='source_ids'})) if source_ids is not None else len(canonical(record))
        if group and size+weight>CHUNK_BYTES:chunks.append(group);group=[];size=0
        if weight>CHUNK_BYTES:raise BrokerError('project_record_limit')
        group.append(record);size+=weight
    if group:chunks.append(group)
    result=[];chunk_source_map={}
    for i,group in enumerate(chunks):
        mapped=sorted({sid for record in group for sid in record['source_ids']})
        if source_ids is not None:group=[{k:v for k,v in r.items() if k!='source_ids'} for r in group]
        chunk={'index':i,'records':group};chunk['chunk_id']=sha(chunk);result.append(chunk);chunk_source_map[chunk['chunk_id']]=mapped
    if len(result)>256:raise BrokerError('project_chunk_limit_256')
    all_ids=sorted(declared_ids)
    ledger={'schema':1,'project_hash':sha(project),'source_ids':all_ids,'source_id_count':len(all_ids),'record_count':len(records),'chunk_count':len(result),'status':'pending','semantic_complete':False,'chunks':[{'chunk_id':c['chunk_id'],'record_ids':[r['record_id'] for r in c['records']],'source_ids':chunk_source_map[c['chunk_id']],'status':'pending'} for c in result]}
    return result,ledger

def acknowledge(text,chunk,ledger):
    try:reply=json.loads(text)
    except (ValueError,TypeError):raise BrokerError('chunk_acknowledgement_invalid') from None
    expected=[r['record_id'] for r in chunk['records']]
    if not isinstance(reply,dict) or reply.get('chunk_id')!=chunk['chunk_id'] or reply.get('record_ids')!=expected or not isinstance(reply.get('analysis'),str):raise BrokerError('chunk_acknowledgement_mismatch')
    if len(reply['analysis'])>32000:raise BrokerError('chunk_analysis_limit')
    entry=next(c for c in ledger['chunks'] if c['chunk_id']==chunk['chunk_id']);entry['status']='acknowledged_by_provider'
    ledger['status']='all_transport_acknowledged' if all(c['status']=='acknowledged_by_provider' for c in ledger['chunks']) else 'partial_transport_acknowledged'
    # An echo is transport evidence only; it never marks a source semantically complete.
    return reply['analysis']
