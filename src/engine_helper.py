"""Original engine on an immutable snapshot with owned child cancellation."""
import json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
child=None

def terminate_child():
    global child
    if child is None:return
    if os.name=='nt':
        child.close();child=None;return
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=2)
    child=None

def cancelled(signum,frame):
    terminate_child()
    raise SystemExit(128+signum)

def main():
    global child
    for name in ('SIGTERM','SIGINT','SIGHUP'):
        if hasattr(signal,name):signal.signal(getattr(signal,name),cancelled)
    try:
        raw=sys.stdin.buffer.read(32*1024*1024+1)
        if len(raw)>32*1024*1024:raise ValueError('Snapshot too large')
        request=json.loads(raw)
        if request.get('action')!='engine-analysis' or request.get('operation') not in ('run','sensitivity'):raise ValueError('Unsupported analysis')
        resources=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='amua-analysis-') as directory:
            temp=Path(directory);model=temp/'model.amua';command=temp/'command.json'
            model.write_text(request['xml']);command.write_text(json.dumps(request))
            with tempfile.TemporaryFile(dir=temp) as output_file:
                try:
                    args=[str(resources/('runtime/bin/java.exe' if os.name=='nt' else 'runtime/bin/java')),'-Xmx768m','-Djava.awt.headless=true',
                        '-Djava.util.prefs.userRoot='+str(temp/'prefs'),'-cp',str(resources/'Amua_0.3.6.jar'),
                        'v21.ChatEngine',str(model),str(command)]
                    if os.name=='nt':
                        from windows_process import Child
                        child=Child(args,output_file)
                    else:
                        args.insert(3,'-Damua.parent.pid='+str(os.getpid()))
                        child=subprocess.Popen(args,stdout=output_file,stderr=subprocess.DEVNULL,start_new_session=True)
                    deadline=time.monotonic()+90
                    while child.poll() is None:
                        if os.fstat(output_file.fileno()).st_size>8*1024*1024:raise ValueError('Engine output limit exceeded')
                        if time.monotonic()>=deadline:raise subprocess.TimeoutExpired(child.args,90)
                        time.sleep(.05)
                    if os.fstat(output_file.fileno()).st_size>8*1024*1024:raise ValueError('Engine output limit exceeded')
                    output_file.seek(0);output=output_file.read(8*1024*1024+1).decode('utf-8')
                finally:terminate_child()
            lines=output.strip().splitlines();data=json.loads(lines[-1]) if lines else {}
            if not data.get('ok'):raise ValueError(data.get('error','Original engine failed; no completed analysis'))
            data['text']='Analysis completed on the inspected model snapshot.\n'+json.dumps(data,indent=2,ensure_ascii=False)
            data['target_hash']=request['target_hash']
    except subprocess.TimeoutExpired:data={'ok':False,'error':{'category':'analysis_deadline','message':'Analysis reached 90 seconds and its process group was stopped. The live model is unchanged.'}}
    except Exception as error:data={'ok':False,'error':{'category':'analysis_failed','message':str(error)[:3000]}}
    finally:terminate_child()
    print(json.dumps(data,ensure_ascii=False,allow_nan=False))
if __name__=='__main__':main()
