"""Elapsed time is informational; only a lack of meaningful stream progress stalls.
Keepalives/unknown/duplicate lifecycle events do not refresh the clock. Never
retain or forward reasoning content: callers receive phase/count metadata only.
"""
import time

DEFAULT_IDLE_SECONDS=180
class ProgressStalled(Exception):pass

def idle_seconds(value=DEFAULT_IDLE_SECONDS):
    if type(value) is not int or not 60<=value<=1800:raise ValueError('invalid_model_wait_time')
    return value

class ProgressWatch:
    DELTAS={'response.output_text.delta':'receiving','response.reasoning_summary_text.delta':'thinking','response.reasoning_text.delta':'thinking'}
    STAGES={'response.created':'thinking','response.in_progress':'thinking','response.output_item.added':'thinking','response.output_item.done':'finishing','response.content_part.added':'thinking','response.content_part.done':'finishing','response.reasoning_summary_part.added':'thinking','response.reasoning_summary_part.done':'thinking','response.output_text.done':'finishing','response.reasoning_summary_text.done':'thinking','response.reasoning_text.done':'thinking'}
    def __init__(self,seconds=DEFAULT_IDLE_SECONDS,clock=None):
        self.seconds=idle_seconds(seconds);self.clock=clock or time.monotonic;self.last=self.clock();self.seen=set();self.sequence=0
    def check(self):
        if self.clock()-self.last>=self.seconds:raise ProgressStalled()
    def accept(self,data):
        self.check();kind=data.get('type');phase=self.DELTAS.get(kind)
        if phase:
            if not isinstance(data.get('delta'),str) or not data['delta']:return None
        elif kind in self.STAGES:
            item=data.get('item') if isinstance(data.get('item'),dict) else {}
            key=(kind,str(data.get('item_id',item.get('id',''))),str(data.get('output_index','')),str(data.get('content_index','')),str(data.get('summary_index','')))
            if key in self.seen or len(self.seen)>=4096:return None
            self.seen.add(key);phase=self.STAGES[kind]
        else:return None
        self.sequence+=1;self.last=self.clock()
        return {'event':'inference_progress','phase':phase,'sequence':self.sequence}
