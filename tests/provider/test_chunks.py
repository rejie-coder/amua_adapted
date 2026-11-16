import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/provider'));sys.path.insert(0,str(ROOT/'src'))
from chunks import partition,acknowledge,canonical,CHUNK_BYTES
from broker import BrokerError

def restored(chunks):
    result={};fragments={}
    def assign(path,value):
        nonlocal result
        if not path:result=value;return
        cur=result
        for i,key in enumerate(path[:-1]):
            nxt=path[i+1]
            if isinstance(cur,list):
                while len(cur)<=key:cur.append(None)
                if cur[key] is None:cur[key]=[] if isinstance(nxt,int) else {}
            elif key not in cur:cur[key]=[] if isinstance(nxt,int) else {}
            cur=cur[key]
        key=path[-1]
        if isinstance(cur,list):
            while len(cur)<=key:cur.append(None)
        cur[key]=value
    for c in chunks:
        for r in c['records']:
            if 'fragment_index' in r:fragments.setdefault(tuple(r['path']),[]).append(r)
            else:assign(r['path'],r['value'])
    for path,rs in fragments.items():assign(list(path),''.join(r['value'] for r in sorted(rs,key=lambda r:r['fragment_index'])))
    return result

class ChunkTests(unittest.TestCase):
    def test_large_lossless_unicode_and_ids(self):
        project={'provenance':{'files':[{'id':'file','records':[{'id':'line-'+str(i),'text':'මියගිය'*1000} for i in range(90)]}]},'graph':{'id':'not-a-source'},'large':'é'*150000}
        chunks,ledger=partition(project)
        self.assertGreater(len(chunks),1);self.assertEqual(restored(chunks),project)
        self.assertEqual(ledger['source_id_count'],91);self.assertNotIn('not-a-source',ledger['source_ids'])
        self.assertEqual(set(ledger['source_ids']),{s for c in chunks for r in c['records'] for s in r['source_ids']})
        self.assertTrue(all(sum(len(canonical(r)) for r in c['records'])<=CHUNK_BYTES for c in chunks))
    def test_incomplete_ack_not_semantic_completion(self):
        chunks,ledger=partition({'provenance':{'files':[{'id':'source'}]}});chunk=chunks[0]
        reply={'chunk_id':chunk['chunk_id'],'record_ids':[r['record_id'] for r in chunk['records']],'analysis':'Unresolved input'}
        self.assertEqual(acknowledge(json.dumps(reply),chunk,ledger),'Unresolved input')
        self.assertEqual(ledger['status'],'all_transport_acknowledged');self.assertFalse(ledger['semantic_complete'])
        for bad in [{**reply,'chunk_id':'other'},{**reply,'record_ids':[]},{**reply,'record_ids':reply['record_ids']*2}]:
            with self.assertRaises(BrokerError):acknowledge(json.dumps(bad),chunk,ledger)
    def test_mutated_record_content_changes_chunk_identity(self):
        project={'provenance':{'files':[{'id':'source','value':1}]}}
        a,_=partition(project);project['provenance']['files'][0]['value']=2;b,_=partition(project)
        self.assertNotEqual(a[0]['chunk_id'],b[0]['chunk_id'])
    def test_real_workbook_full_scope(self):
        from workflow.core import intake,source_items
        if not (ROOT/'evidence/inputs/D2P cost analysis Cluster care.xlsx').exists():self.skipTest('Private scientific acceptance workbooks are not distributed; public transport fixture runs separately')
        for name,cells,errors in [('D2P cost analysis Cluster care.xlsx',520,0),('CKD Decision Tree WITH SENSITIVITY ANALYSIS.xlsx',2269,24)]:
            project=intake([str(ROOT/'evidence/inputs'/name)])
            chunks,ledger=partition(project)
            self.assertEqual(restored(chunks),project)
            expected={s for f in project['provenance']['files'] for s in source_items(f)}
            self.assertEqual(set(ledger['source_ids']),expected)
            self.assertEqual({s for c in chunks for r in c['records'] for s in r['source_ids']},expected)
            actual_cells=[c for f in project['provenance']['files'] for s in f.get('sheets',[]) for c in s['cells']]
            self.assertEqual(len(actual_cells),cells);self.assertEqual(sum(c['value_kind']=='source-error' for c in actual_cells),errors)
            print(name+': '+str(len(canonical(project)))+' project bytes; '+str(len(chunks))+' chunks; '+str(len(expected))+' exact source IDs')
if __name__=='__main__':unittest.main(verbosity=2)
