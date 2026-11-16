import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src')]
from transport import prepare_transport,encode,decode,MARKER,ESCAPE
from chunks import partition
from test_chunks import restored
from test_provider import MemoryKeys
from broker import Broker,BrokerError
import provider_helper
class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from workflow_helper import dispatch
        source=ROOT/'evidence/inputs/CKD Decision Tree WITH SENSITIVITY ANALYSIS.xlsx';cls.private=source.exists()
        if not cls.private:
            sys.path.insert(0,str(ROOT/'tests'));from public_fixtures import workbook
            cls.fixture_directory=tempfile.TemporaryDirectory();source=workbook(cls.fixture_directory.name)
        cls.project=dispatch({'action':'intake','paths':[str(source)]})['project']
        cls.transport,cls.meta=prepare_transport(cls.project)
        cls.chunks,cls.ledger=partition(cls.transport,cls.meta['source_ids'])
    def test_actual_dispatch_full_project_fits_and_reconstructs(self):
        self.assertGreater(len(self.chunks),1);self.assertEqual(decode(restored(self.chunks)['project']),self.project)
        self.assertGreater(len(self.project['graph']['nodes']),2269)
        files=self.project['provenance']['files'];self.assertEqual(len(files[0]['sheets']),6)
        cells=[c for s in files[0]['sheets'] for c in s['cells']]
        self.assertEqual(len(cells),2269);self.assertEqual(sum(c['value_kind']=='source-error' for c in cells),24)
    def test_source_ids_and_drawing_geometry_preserved(self):
        decoded=decode(self.transport['project']);self.assertGreaterEqual(self.meta['source_id_count'],2269)
        self.assertEqual(set(self.meta['source_ids']),{s for chunk in self.ledger['chunks'] for s in chunk['source_ids']})
        for before,after in zip(self.project['provenance']['files'],decoded['provenance']['files']):
            self.assertEqual(before['drawing_parts'],after['drawing_parts']);self.assertEqual(before['media_parts'],after['media_parts']);self.assertEqual(before['parts'],after['parts']);self.assertEqual(before['dependencies'],after['dependencies'])
    def test_each_table_row_group_keeps_headers_inside_one_record(self):
        paths=[]
        def walk(value,path):
            if isinstance(value,dict):
                if MARKER in value:
                    for i,group in enumerate(value[MARKER]):
                        self.assertIn('columns',group);self.assertIn('row_format',group);paths.append(path+[MARKER,i])
                for k,v in value.items():walk(v,path+[k])
            elif isinstance(value,list):
                for i,v in enumerate(value):walk(v,path+[i])
        walk(self.transport,[])
        records=[r['path'] for c in self.chunks for r in c['records']]
        for path in paths:self.assertTrue(any(path[:len(r)]==r for r in records),'A table row group lost its independent header context')
    def test_missing_null_reserved_keys_and_unicode_roundtrip(self):
        value={'rows':[{'a':None,'b':'සිංහල'},{'a':2},{MARKER:3,ESCAPE:4}]}
        self.assertEqual(decode(encode(value)),value)
    def test_approval_hash_change_rejected_before_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            b=Broker(temp,MemoryKeys())
            with patch.object(provider_helper,'Broker',return_value=b),patch.object(b,'models',side_effect=AssertionError('catalog forbidden')):
                with self.assertRaisesRegex(BrokerError,'transport_approval_required'):
                    provider_helper.run({'action':'request','text':'test','project':{'value':1},'approved_transport_hash':'wrong','approved_max_calls':1,'budget_session_id':'synthetic-session-uuid'})
    def test_old_ui_transport_hash_error_has_restart_message(self):
        class Input:
            buffer=io.BytesIO(b'{"action":"request"}')
        output=io.StringIO()
        with patch.object(provider_helper.sys,'stdin',Input()),patch.object(provider_helper.sys,'stdout',output),patch.object(provider_helper,'run',side_effect=BrokerError('transport_approval_required')):
            provider_helper.main()
        result=json.loads(output.getvalue());self.assertFalse(result['ok']);self.assertEqual(result['error']['category'],'transport_approval_required');self.assertIn('Save your model, quit Amua and reopen',result['error']['message'])
    def test_preview_allows_more_than_old_session_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            b=Broker(temp,MemoryKeys())
            with patch.object(provider_helper,'Broker',return_value=b),patch.object(provider_helper,'partition',return_value=([{}]*33,{'source_id_count':0,'project_hash':'synthetic'})):
                result=provider_helper.run({'action':'preview','text':'test','project':{'value':1},'budget_session_id':'synthetic-session-uuid'})
            self.assertTrue(result['feasible']);self.assertEqual(result['required_calls'],33);self.assertIsNone(result['remaining_calls']);self.assertIsNone(result['session_call_limit'])
if __name__=='__main__':unittest.main(verbosity=2)
