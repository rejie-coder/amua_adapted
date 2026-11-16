"""Visible finite folder plans and progressive parsing, with no silent omissions."""
import copy
import os
import stat
from pathlib import Path
from .core import (WorkflowError,uid,digest,encoded,intake,source_items,source_scope_draft,project_budget)

def selection_plan(paths,options=None):
    options=options or {};recursive=options.get('recursive',False);hidden=options.get('include_hidden',False)
    if not isinstance(recursive,bool) or not isinstance(hidden,bool):raise WorkflowError('Folder scope options must be booleans')
    maximum=int(options.get('max_entries',10000))
    if not 1<=maximum<=10000:raise WorkflowError('Selection plan supports at most 10,000 metadata entries')
    entries=[];exclusions=[];seen=set()
    def visit(path,display,depth):
        if len(entries)+len(exclusions)>=maximum:raise WorkflowError('Selection enumeration limit reached; select explicit smaller folders. No truncated plan is returned')
        if depth>20:raise WorkflowError('Folder depth limit reached; narrow the selected scope')
        if path.is_symlink():exclusions.append({'name':display,'reason':'symlink excluded'});return
        if path.name.startswith('.') and not hidden:exclusions.append({'name':display,'reason':'hidden item excluded'});return
        info=path.stat()
        if stat.S_ISDIR(info.st_mode):
            if depth>0 and not recursive:exclusions.append({'name':display,'reason':'nested folder excluded; recursive selection was not enabled'});return
            for child in sorted(path.iterdir()):visit(child,display+'/'+child.name,depth+1)
        elif stat.S_ISREG(info.st_mode):
            key=(info.st_dev,info.st_ino,str(path))
            if key in seen:exclusions.append({'name':display,'reason':'same selected path repeated'});return
            seen.add(key)
            entries.append({'id':uid(),'index':len(entries),'path':str(path),'display_path':display,'bytes':info.st_size,'mtime_ns':str(info.st_mtime_ns),'device':str(info.st_dev),'inode':str(info.st_ino),'status':'pending'})
        else:exclusions.append({'name':display,'reason':'special file excluded'})
    for value in paths:
        path=Path(value).absolute()
        if any(p.is_symlink() for p in path.parents):raise WorkflowError('Symlink parent selection is unsupported')
        visit(path,path.name,0)
    return {'id':uid(),'revision':0,'options':{'recursive':recursive,'include_hidden':hidden},'entries':entries,'exclusions':exclusions,
            'selected_bytes':sum(e['bytes'] for e in entries),'batch_size':20,'status':'pending' if entries else 'empty','limits':{'max_entries':maximum,'max_files_per_batch':20,'default_file_bytes':25*1024*1024,'default_batch_bytes':100*1024*1024},
            'note':'A plan inventories names and metadata only. No pending source has been semantically processed. Parse explicit batches, then review every failed/unsupported entry.'}

def merge_projects(target,incoming):
    if target is None:return project_budget(incoming)
    target=copy.deepcopy(target)
    existing={f['id'] for f in target['provenance']['files']}
    new=[f for f in incoming['provenance']['files'] if f['id'] not in existing]
    target['provenance']['files'].extend(new)
    target['provenance']['coverage'].extend({'source_id':identity,'status':'unresolved','reason':'Progressively inventoried; semantic interpretation pending'} for f in new for identity in source_items(f))
    target['source_set_hash']=digest(encoded([(f['id'],f['sha256']) for f in target['provenance']['files']]))
    target['revision']+=1;target['state']='draft_incomplete'
    return project_budget(target)

def intake_batch(selection,offset=0,count=20,project=None,options=None):
    if not isinstance(offset,int) or not isinstance(count,int) or offset<0 or not 1<=count<=20:raise WorkflowError('Batch requires nonnegative offset and count 1–20')
    updated=copy.deepcopy(selection);entries=updated['entries'];total=0;processed=[]
    for entry in entries[offset:offset+count]:
        path=Path(entry['path'])
        try:
            if path.is_symlink() or any(p.is_symlink() for p in path.parents):raise WorkflowError('Selected source became a symlink')
            info=path.stat()
            if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)!=(int(entry['device']),int(entry['inode']),entry['bytes'],int(entry['mtime_ns'])):raise WorkflowError('Selected source changed after the folder snapshot')
            total+=entry['bytes']
            if total>int((options or {}).get('max_total_bytes',100*1024*1024)):raise WorkflowError('Batch byte limit reached; retry this source in a smaller explicit batch')
            settings=dict(options or {},selection_offset=entry['index'],selection_identity=selection['id']+':'+str(entry['index']))
            incoming=intake([str(path)],settings);source=incoming['provenance']['files'][0];source['relative_name']=entry['display_path'];source['selection_plan_id']=selection['id']
            project=merge_projects(project,incoming)
            entry['status']='failed' if source['kind']=='parse-error' else ('unsupported' if source['kind']=='unsupported' else 'inventoried')
            entry['source_id']=source['id'];entry['sha256']=source['sha256']
        except Exception as exc:
            entry['status']='failed';entry['error_category']=type(exc).__name__;entry['reason']=str(exc) if isinstance(exc,WorkflowError) else 'Source could not be read or parsed; still unresolved'
        processed.append(entry['id'])
    updated['revision']+=1
    pending=sum(e['status']=='pending' for e in entries);failed=sum(e['status'] in ('failed','unsupported') for e in entries)
    updated['status']='incomplete' if pending or failed else 'inventoried-unreviewed'
    if project is not None:
        project['provenance']['selection_scope']={'id':selection['id'],'entries':[{k:v for k,v in e.items() if k not in ('path','device','inode','mtime_ns')} for e in entries],'exclusions':selection['exclusions'],'status':updated['status']}
        try:project=source_scope_draft(project)
        except WorkflowError as exc:
            # Physical source ledger remains intact even when full graph display
            # exceeds its independently bounded 10k-node envelope.
            project['graph']={'nodes':[],'scope':'presentation pending; physical inventory retained','display_limit_reason':str(exc)};project['state']='draft_incomplete'
    return {'selection':updated,'project':project,'processed_entry_ids':processed,'next_offset':min(offset+count,len(entries)),'pending':pending,'failed_or_unsupported':failed}
