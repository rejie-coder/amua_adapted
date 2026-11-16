"""Reversible columnar full-project wire view, with headers on every row group.
No source/model/display fields are omitted. The original project is never edited.
"""
import json
from broker import BrokerError
from chunks import canonical,sha,nested_ids
FORMAT='amua-columnar-project-v1'
GROUP_BYTES=24*1024
MARKER='$amua_table_v1'
ESCAPE='$amua_escaped_object_v1'

def encode(value):
    if isinstance(value,dict):
        result={k:encode(v) for k,v in value.items()}
        if MARKER in result or ESCAPE in result:return {ESCAPE:[[k,v] for k,v in result.items()]}
        return result
    if not isinstance(value,list):return value
    if not value or not all(isinstance(r,dict) for r in value):return [encode(v) for v in value]
    columns=sorted({k for row in value for k in row})
    groups=[];rows=[]
    def group(rs,start):return {'columns':columns,'row_start':start,'rows':rs,'row_format':'presence bit mask followed by values in columns order; zero bit means absent field'}
    start=0
    for original in value:
        mask=sum(1<<i for i,k in enumerate(columns) if k in original)
        row=[hex(mask)]+[encode(original[k]) if k in original else None for k in columns]
        if len(canonical(group([row],0)))>GROUP_BYTES:
            # A huge nested row would separate its headers during generic partitioning.
            # Keep that table as ordinary self-describing objects instead.
            return [encode(r) for r in value]
        prospective=group(rows+[row],start)
        if rows and len(canonical(prospective))>GROUP_BYTES:
            groups.append(group(rows,start));start+=len(rows);rows=[]
        rows.append(row)
    if rows:groups.append(group(rows,start))
    return {MARKER:groups,'row_count':len(value)}

def decode(value):
    if isinstance(value,list):return [decode(v) for v in value]
    if not isinstance(value,dict):return value
    if set(value)=={ESCAPE}:return {k:decode(v) for k,v in value[ESCAPE]}
    if set(value)=={MARKER,'row_count'}:
        rows=[]
        for group in value[MARKER]:
            if group.get('row_start')!=len(rows):raise BrokerError('transport_row_order_invalid')
            columns=group['columns']
            if len(set(columns))!=len(columns):raise BrokerError('transport_columns_invalid')
            for row in group['rows']:
                if len(row)!=len(columns)+1:raise BrokerError('transport_row_invalid')
                mask=int(row[0],16)
                if mask<0 or mask>=(1<<len(columns)):raise BrokerError('transport_row_invalid')
                rows.append({k:decode(row[i+1]) for i,k in enumerate(columns) if mask & (1<<i)})
        if len(rows)!=value['row_count']:raise BrokerError('transport_row_count_invalid')
        return rows
    return {k:decode(v) for k,v in value.items()}

def prepare_transport(project):
    if not isinstance(project,dict):raise BrokerError('invalid_project')
    payload={'transport_format':FORMAT,'original_project_hash':sha(project),'scope':'Complete project in reversible columnar tables; no source, scientific, question, graph or layout fields omitted. Every table row group carries its own columns. Presence mask preserves absent versus null fields. Transport acknowledgment is not scientific completeness.','project':encode(project)}
    if decode(payload['project'])!=project:raise BrokerError('transport_roundtrip_failed')
    sources=sorted(set(nested_ids(project.get('provenance',{}).get('files',[]))))
    return payload,{'transport_format':FORMAT,'original_project_hash':payload['original_project_hash'],'transport_hash':sha(payload),'source_id_count':len(sources),'scope':payload['scope'],'source_ids':sources}
