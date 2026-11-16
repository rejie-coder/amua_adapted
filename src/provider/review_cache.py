"""Bound, atomic source-review checkpoints; never prompts, credentials or raw chat."""
try:
    import fcntl
except ImportError:
    import windows_locking as fcntl
import json
import os
import sys
from pathlib import Path
from broker import BrokerError
from chunks import canonical,sha

def binding_for(command,transport_meta,model,broker):
    return {'transport_hash':transport_meta['transport_hash'],'original_project_hash':transport_meta['original_project_hash'],
            'question_hash':sha(command.get('text','')),'history_hash':sha(command.get('history',[])),
            'model':model,'account_binding':sha({'registration':broker.meta.get('active'),'epoch':broker.meta.get('epoch')}),
            'budget_session_hash':sha(command.get('budget_session_id'))}

class ReviewCache:
    def __init__(self,support,binding,chunks,ledger):
        self.binding=binding;self.binding_hash=sha(binding);self.chunks=chunks;self.ledger=ledger
        self.directory=Path(support)/'source-review-checkpoints'
        self.directory.mkdir(mode=0o700,exist_ok=True)
        if self.directory.is_symlink():raise BrokerError('unsafe_review_directory')
        os.chmod(self.directory,0o700)
        self.path=self.directory/(self.binding_hash+'.json');self.accepted={};self.failure=None;self.lock_fd=None
        self.load()
    def load(self):
        if not self.path.exists():return
        if self.path.is_symlink() or self.path.stat().st_size>16*1024*1024:raise BrokerError('review_checkpoint_invalid')
        try:
            data=json.loads(self.path.read_text());checksum=data.pop('checksum')
            if sha(data)!=checksum or data.get('schema')!=1 or data.get('binding')!=self.binding:raise ValueError()
            expected={c['chunk_id']:[r['record_id'] for r in c['records']] for c in self.chunks}
            if data.get('chunk_ids')!=[c['chunk_id'] for c in self.chunks]:raise ValueError()
            accepted=data['accepted']
            if not isinstance(accepted,dict):raise ValueError()
            for key,record in accepted.items():
                if key not in expected or record.get('record_ids')!=expected[key] or not isinstance(record.get('analysis'),str) or len(record['analysis'])>32000 or sha(record['analysis'])!=record.get('analysis_hash'):raise ValueError()
            self.accepted=accepted;self.failure=data.get('failure')
        except (ValueError,KeyError,TypeError,OSError):raise BrokerError('review_checkpoint_invalid') from None
    def acquire(self):
        self.lock_fd=os.open(self.path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR,0o600)
        try:fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock_fd);self.lock_fd=None;raise BrokerError('review_in_progress') from None
        self.load()
    def close(self):
        if self.lock_fd is not None:os.close(self.lock_fd);self.lock_fd=None
    def progress(self):
        completed=len(self.accepted);total=len(self.chunks)
        return {'completed_chunks':completed,'total_calls':total,'required_calls':total-completed,
                'resume_available':completed>0,'review_binding_hash':self.binding_hash,
                'review_state':'complete' if completed==total else ('partial' if completed else 'pending')}
    def pending(self):return [c for c in self.chunks if c['chunk_id'] not in self.accepted]
    def restore_ledger(self):
        for entry in self.ledger['chunks']:
            entry['status']='acknowledged_by_provider' if entry['chunk_id'] in self.accepted else 'pending'
        completed=len(self.accepted)
        self.ledger['status']='all_transport_acknowledged' if completed==len(self.chunks) else ('partial_transport_acknowledged' if completed else 'pending')
        self.ledger['semantic_complete']=False
        return self.ledger
    def save(self):
        data={'schema':1,'binding':self.binding,'binding_hash':self.binding_hash,
              'chunk_ids':[c['chunk_id'] for c in self.chunks],'accepted':self.accepted,
              'source_ids':self.ledger['source_ids'],'source_id_count':self.ledger['source_id_count'],
              'failure':self.failure,'semantic_complete':False,'analysis_status':'Schema/terminal/receipt checked; scientific meaning unreviewed. Source review summaries only; no raw prompts/history/chat.'}
        data['checksum']=sha(data);raw=canonical(data)
        if len(raw)>16*1024*1024:raise BrokerError('review_checkpoint_limit')
        temp=self.directory/(self.path.name+'.tmp-'+os.urandom(8).hex())
        fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.path)
            if sys.platform!='win32':
                directory=os.open(self.directory,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
            # Windows has no portable directory fsync via Python os.open.
            # File flush + atomic replacement are used; native crash durability needs Windows evidence.
        finally:
            if temp.exists():temp.unlink()
    def commit(self,chunk,analysis):
        previous=dict(self.accepted);previous_failure=self.failure
        self.accepted[chunk['chunk_id']]={'record_ids':[r['record_id'] for r in chunk['records']],
                                         'analysis':analysis,'analysis_hash':sha(analysis)}
        self.failure=None
        try:self.save()
        except (BrokerError,OSError):
            self.accepted=previous;self.failure=previous_failure;self.restore_ledger();raise BrokerError('review_checkpoint_write_failed') from None
        self.restore_ledger()
    def fail(self,category,index):
        self.failure={'category':category,'failed_chunk_index':index};self.save()
    def analyses(self):return [self.accepted[c['chunk_id']]['analysis'] for c in self.chunks if c['chunk_id'] in self.accepted]
