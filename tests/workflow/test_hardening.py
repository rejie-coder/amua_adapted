import copy,fcntl,json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from workflow.core import intake,refresh_pdf_batch,source_items,validate_graph,encoded,WorkflowError,save_project,synthetic_project
from workflow.batches import merge_projects
ROOT=Path(__file__).resolve().parents[2]

class WorkflowHardeningTests(unittest.TestCase):
    def test_resume_pdf_page_retains_source_identity_and_coverage(self):
        fixture=ROOT/'tests/workflow/fixtures/synthetic-scanned-english.pdf'
        failure={'status':'unreadable','reason_category':'synthetic-unreadable','text':'','regions':[]}
        success={'status':'ok','text':'Synthetic 125 LKR','confidence':.9,'regions':[{'text':'125 LKR','confidence':.9,'bounds':[0,0,1,1]}],'language':'en-US'}
        with patch('workflow.mixed_formats.LocalOCR.page',return_value=failure):before=intake([str(fixture)])
        ident=before['provenance']['files'][0]['id'];original=encoded(before)
        with patch('workflow.mixed_formats.LocalOCR.page',return_value=success):after=refresh_pdf_batch(before,str(fixture),1,1)
        source=after['provenance']['files'][0]
        self.assertEqual(ident,source['id']);self.assertEqual(source['pages'][0]['status'],'ocr-extracted-unreviewed')
        self.assertTrue(any(r['kind']=='pdf-ocr-region' for r in source['records']))
        self.assertTrue(validate_graph(after));self.assertEqual(original,encoded(before))
        self.assertEqual(len({c['source_id'] for c in after['provenance']['coverage']}),len(after['provenance']['coverage']))

    def test_invalid_ocr_batch_rejected(self):
        from workflow.mixed_formats import pdf
        data=(ROOT/'tests/workflow/fixtures/synthetic-scanned-english.pdf').read_bytes()
        for start,count in ((0,1),(1,21),(True,1)):
            with self.assertRaises(WorkflowError):pdf(data,'synthetic',ocr_helper=False,ocr_start=start,ocr_count=count)

    def test_aggregate_inventory_budget_preserves_previous_project(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            a=Path(directory)/'a.txt';b=Path(directory)/'b.txt';a.write_text('a'*2000);b.write_text('b'*2000)
            first=intake([str(a)]);second=intake([str(b)]);before=encoded(first)
            with patch('workflow.core.MAX_PROJECT_BYTES',len(before)+100):
                with self.assertRaises(WorkflowError):merge_projects(first,second)
            self.assertEqual(before,encoded(first))

    def test_killed_writer_releases_os_lock_without_manual_deletion(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)/'project.amuax';lock=path.with_suffix('.amuax.lock')
            script='import fcntl,os,sys,time;f=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(f,fcntl.LOCK_EX);print("ready",flush=True);time.sleep(30)'
            writer=subprocess.Popen([sys.executable,'-c',script,str(lock)],stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(writer.stdout.readline().strip(),'ready')
                with self.assertRaisesRegex(WorkflowError,'locked'):save_project(synthetic_project(),path)
                writer.kill();writer.wait(timeout=3)
                self.assertTrue(lock.exists());self.assertTrue(save_project(synthetic_project(),path)['sha256'])
            finally:
                if writer.poll() is None:writer.kill();writer.wait()
                writer.stdout.close()
if __name__=='__main__':unittest.main()
