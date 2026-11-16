"""Clock-driven long-stream/stall checks: no real provider, keys, sleeps or billing."""
import json,sys,tempfile,socket,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/provider'))
from progress_watch import ProgressWatch,ProgressStalled,idle_seconds
import broker

class Clock:
 def __init__(self):self.now=0
 def __call__(self):return self.now
 def advance(self,seconds):self.now+=seconds
class Stream:
 def __init__(self,clock,events):self.clock=clock;self.events=events;self.closed=False
 def __enter__(self):return self
 def __exit__(self,*args):self.closed=True
 def __iter__(self):
  for seconds,data in self.events:
   self.clock.advance(seconds)
   if isinstance(data,Exception):raise data
   if data is None:yield b': keepalive\n';continue
   yield ('data: '+json.dumps(data)+'\n').encode();yield b'\n'
class Key:
 def close(self):pass
class ProgressTests(unittest.TestCase):
 def make_broker(self,temp):
  b=broker.Broker(support=Path(temp),keychain=Key());b.credentials=lambda:{'access_token':'synthetic_token_never_real'};return b
 def test_output_can_continue_for_many_minutes(self):
  clock=Clock();watch=ProgressWatch(180,clock)
  for i in range(30):clock.advance(60);self.assertEqual(watch.accept({'type':'response.output_text.delta','delta':'model part'} )['phase'],'receiving')
  self.assertEqual(clock.now,1800);watch.check()
 def test_actual_broker_stream_crosses_both_old_deadlines(self):
  with tempfile.TemporaryDirectory() as temp:
   clock=Clock();events=[(0,{'type':'response.created'})]+[(60,{'type':'response.output_text.delta','delta':'part'+str(i)}) for i in range(12)]+[(0,{'type':'response.completed'}),(999,RuntimeError('Must close at completion instead of waiting for EOF'))]
   stream=Stream(clock,events);seen=[]
   with patch.object(broker.time,'monotonic',clock),patch.object(broker.urllib.request,'urlopen',return_value=stream) as open_call:
    result=self.make_broker(temp).request('synthetic',[{'role':'user','content':'fixture'}],emit=seen.append,idle_timeout=180)
   self.assertTrue(result['completed']);self.assertEqual(clock.now,720);self.assertEqual(sum(e['event']=='delta' for e in seen),12);self.assertTrue(stream.closed);self.assertEqual(open_call.call_args.kwargs['timeout'],180)
 def test_keepalive_does_not_refresh_idle(self):
  with tempfile.TemporaryDirectory() as temp:
   clock=Clock();stream=Stream(clock,[(60,None),(60,None),(60,None)]);b=self.make_broker(temp)
   with patch.object(broker.time,'monotonic',clock),patch.object(broker.urllib.request,'urlopen',return_value=stream):
    with self.assertRaisesRegex(broker.BrokerError,'model_chat_stalled'):b.request('synthetic',[{'role':'user','content':'fixture'}],idle_timeout=180)
   self.assertTrue(stream.closed)
 def test_stall_after_real_output(self):
  clock=Clock();watch=ProgressWatch(180,clock);clock.advance(100);watch.accept({'type':'response.output_text.delta','delta':'text'});clock.advance(179);watch.check();clock.advance(1)
  with self.assertRaises(ProgressStalled):watch.check()
 def test_repeated_lifecycle_and_empty_delta_do_not_fake_progress(self):
  clock=Clock();watch=ProgressWatch(180,clock);watch.accept({'type':'response.in_progress','sequence_number':1});clock.advance(100)
  self.assertIsNone(watch.accept({'type':'response.in_progress','sequence_number':99}));self.assertIsNone(watch.accept({'type':'response.output_text.delta','delta':''}));clock.advance(80)
  with self.assertRaises(ProgressStalled):watch.check()
 def test_reasoning_progress_only_metadata_is_forwarded(self):
  with tempfile.TemporaryDirectory() as temp:
   clock=Clock();events=[(60,{'type':'response.reasoning_summary_text.delta','delta':'private synthetic reasoning content'}) for _ in range(5)]+[(0,{'type':'response.output_text.delta','delta':'visible output'}),(0,{'type':'response.completed'})];seen=[]
   with patch.object(broker.time,'monotonic',clock),patch.object(broker.urllib.request,'urlopen',return_value=Stream(clock,events)):
    self.make_broker(temp).request('synthetic',[{'role':'user','content':'fixture'}],emit=seen.append,idle_timeout=180)
   self.assertNotIn('private synthetic reasoning',json.dumps(seen));self.assertEqual(sum(e.get('phase')=='thinking' for e in seen),5)
 def test_socket_silence_becomes_stall_category(self):
  with tempfile.TemporaryDirectory() as temp:
   with patch.object(broker.urllib.request,'urlopen',side_effect=socket.timeout()):
    with self.assertRaisesRegex(broker.BrokerError,'model_chat_stalled'):self.make_broker(temp).request('synthetic',[{'role':'user','content':'fixture'}],idle_timeout=180)
 def test_legacy_requests_retain_network_timeout_category(self):
  with tempfile.TemporaryDirectory() as temp:
   with patch.object(broker.urllib.request,'urlopen',side_effect=socket.timeout()) as open_call:
    with self.assertRaisesRegex(broker.BrokerError,'network_timeout'):self.make_broker(temp).request('synthetic',[{'role':'user','content':'fixture'}])
   self.assertEqual(open_call.call_args.kwargs['timeout'],30)
 def test_cancelled_and_stale_responses_still_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   clock=Clock();b=self.make_broker(temp)
   def emit(event):b.cancelled.set()
   with patch.object(broker.time,'monotonic',clock),patch.object(broker.urllib.request,'urlopen',return_value=Stream(clock,[(0,{'type':'response.created'}),(1,{'type':'response.output_text.delta','delta':'x'})])):
    with self.assertRaisesRegex(broker.BrokerError,'cancelled'):b.request('synthetic',[{'role':'user','content':'fixture'}],emit=emit,idle_timeout=180)
 def test_setting_bounds_and_shorter_custom_stall(self):
  for value in (None,True,0,59,1801,180.5,'180'):
   with self.assertRaises(ValueError):idle_seconds(value)
  for value in (60,120,180,300,600,1800):self.assertEqual(idle_seconds(value),value)
  clock=Clock();watch=ProgressWatch(60,clock);clock.advance(60)
  with self.assertRaises(ProgressStalled):watch.check()
if __name__=='__main__':unittest.main()
