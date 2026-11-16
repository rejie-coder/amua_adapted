#!/usr/bin/env python3
"""Single bounded JSON request/reply helper. Never executes source instructions."""
import json
import sys
import signal
try:
    import resource
except ImportError:
    resource=None
import os
import threading
from workflow.core import (WorkflowError, intake, d2p_draft, save_project,
                           open_project, answer_question, summary, synthetic_project, synthetic_preview, digest, source_scope_draft, build_chunk_ledger)

def dispatch(request):
    action=request.get('action')
    if action=='intake':
        paths=request.get('paths')
        if not isinstance(paths,list) or any(not isinstance(p,str) for p in paths):raise WorkflowError('paths must be a list of selected file paths')
        project=intake(paths,request.get("options"))
        if {'D2P cost analysis Cluster care.xlsx','d2p_tree_v2.png','d2p_tree.png'} <= {f['name'] for f in project['provenance']['files']}:
            project=d2p_draft(project)
        else:
            project=source_scope_draft(project)
    elif action=='selection-plan':
        from workflow.batches import selection_plan
        return {'ok':True,'selection':selection_plan(request['paths'],request.get('options'))}
    elif action=='intake-batch':
        from workflow.batches import intake_batch
        result=intake_batch(request['selection'],request.get('offset',0),request.get('count',20),request.get('project'),request.get('options'))
        if result['project'] is not None:result['summary']=summary(result['project'])
        return dict(ok=True,**result)
    elif action=='ocr-batch':
        from workflow.core import refresh_pdf_batch
        project=refresh_pdf_batch(request['project'],request['path'],request.get('start_page',1),request.get('page_count',20))
    elif action=='prepare-digest':project=build_chunk_ledger(request['project'])
    elif action=='draft-source-scope':project=source_scope_draft(request['project'])
    elif action=='draft-d2p':project=d2p_draft(request['project'])
    elif action=='save':
        return {'ok':True,'saved':save_project(request['project'],request['path'],request.get('expected_hash'))}
    elif action=='open':
        from pathlib import Path
        project=open_project(request['path'],request.get('recover',False))
        return {'ok':True,'project':project,'summary':summary(project),'archive_hash':digest(__import__('workflow.core',fromlist=['read_project_bytes']).read_project_bytes(request['path']))}
    elif action=='synthetic':project=synthetic_project()
    elif action=='preview-synthetic':return {'ok':True,'preview':synthetic_preview(request['project'])}
    elif action=='answer':project=answer_question(request['project'],request['question_id'],request['value'],request['unit'],request['expected_revision'])
    else:raise WorkflowError('Unsupported workflow action')
    return {'ok':True,'project':project,'summary':summary(project)}

def main():
    def cancelled(signum,frame):raise SystemExit(128+signum)
    for name in ('SIGTERM','SIGINT','SIGHUP'):
        if hasattr(signal,name):signal.signal(getattr(signal,name),cancelled)
    if os.name=='nt':
        from windows_process import limit_current_process
        try:limit_current_process()
        except OSError:
            sys.stdout.write(json.dumps({'ok':False,'error':{'category':'resource_guard_unavailable','message':'Windows could not establish safe parsing limits; no input was processed.'}}));return
        def expired():
            sys.stdout.write(json.dumps({'ok':False,'error':{'category':'source_deadline','message':'Local parsing reached its 120-second budget; select smaller source groups.'}}));sys.stdout.flush();os._exit(124)
        watchdog=threading.Timer(120,expired);watchdog.daemon=True;watchdog.start()
    else:
        def deadline(signum,frame):raise WorkflowError('Local parsing reached its 120-second budget; narrow the source or use a PDF page batch')
        def memory_limit(signum,frame):raise WorkflowError('Local parsing reached its 768 MiB memory budget; select smaller source groups')
        signal.signal(signal.SIGUSR1,memory_limit)
        def monitor_memory():
            while True:
                import time
                time.sleep(.25)
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if sys.platform!='darwin':peak*=1024
                if peak>768*1024*1024:os.kill(os.getpid(),signal.SIGUSR1);return
        threading.Thread(target=monitor_memory,daemon=True,name='Amua source memory budget').start()
        signal.signal(signal.SIGALRM,deadline);signal.alarm(120)
        resource.setrlimit(resource.RLIMIT_CPU,(90,95))
    try:
        data=sys.stdin.buffer.read(32*1024*1024+1)
        if len(data)>32*1024*1024:raise WorkflowError('Request limit exceeded')
        request=json.loads(data)
        if not isinstance(request,dict):raise WorkflowError('Request must be an object')
        result=dispatch(request)
    except Exception as exc:
        # Whitelisted validation messages; never dump exception paths/content.
        message=str(exc) if isinstance(exc,WorkflowError) else 'Selected input or project could not be processed; no executable output was produced.'
        result={'ok':False,'error':{'category':type(exc).__name__,'message':message}}
    if os.name=='nt':watchdog.cancel()
    else:signal.alarm(0)
    output=json.dumps(result,ensure_ascii=False,allow_nan=False)
    if len(output.encode())>24*1024*1024:output=json.dumps({'ok':False,'error':{'category':'project_limit','message':'Prepared inventory exceeds 24 MiB transport budget; select smaller source groups.'}})
    sys.stdout.write(output)

if __name__=='__main__':main()
