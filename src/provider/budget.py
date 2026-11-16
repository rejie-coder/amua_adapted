"""Cross-process usage counter. No application session-call limit is enforced."""
try:
    import fcntl
except ImportError:
    import windows_locking as fcntl
import json
import os
import re
from broker import BrokerError
LIMIT=None

def operate(support,session,consume=False):
    if not isinstance(session,str) or not re.fullmatch('[A-Za-z0-9_-]{16,80}',session):raise BrokerError('invalid_budget_session')
    path=support/'call-budgets.json';lock=os.open(support/'call-budgets.lock',os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX)
        values=json.loads(path.read_text()) if path.exists() else {}
        used=values.get(session,0)
        if type(used) is not int or used<0:raise BrokerError('budget_state_invalid')
        if consume:
            used+=1;values[session]=used
            temp=path.with_name(path.name+'.tmp-'+os.urandom(8).hex())
            fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as f:json.dump(values,f);f.flush();os.fsync(f.fileno())
            os.replace(temp,path)
        return {'calls_used':used,'session_call_limit':LIMIT,'remaining_calls':None,'session_limit_enforced':False}
    finally:os.close(lock)
