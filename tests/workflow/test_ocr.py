import json
import math
import os
import stat
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/dependencies/python'))
from workflow.mixed_formats import pdf, LocalOCR, native_ocr_helper
from workflow.core import intake,source_scope_draft,build_chunk_ledger,source_items,validate_graph
from collections import Counter

FIXTURE=ROOT/'tests/workflow/fixtures/synthetic-scanned-english.pdf'

class OCRTests(unittest.TestCase):
    def test_no_helper_retains_scanned_page_and_explicit_reason(self):
        f=pdf(FIXTURE.read_bytes(),'no-helper',ocr_helper=False)
        self.assertEqual(f['page_count'],1);page=f['pages'][0]
        self.assertEqual(page['status'],'unreadable-scanned-page');self.assertFalse(page['text'].strip())
        self.assertEqual(page['ocr']['reason_category'],'native-helper-unavailable')
        self.assertEqual(f['ocr'],'unavailable; no OCR performed')
        self.assertTrue(f['parse_issues'])
    def test_private_snapshot_cleanup_and_low_confidence_is_unreviewed(self):
        seen=[]
        def fake_run(command,**kwargs):
            path=Path(command[command.index('--pdf')+1]);seen.append(path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(path.read_bytes(),FIXTURE.read_bytes())
            self.assertEqual(kwargs['timeout'],20);self.assertEqual(command[-1],'8000000')
            return SimpleNamespace(returncode=0,stdout=json.dumps({'status':'ok','page':1,'text':'Price 125 LKR','confidence':0.4,'language':'en-US','regions':[{'text':'Price 125 LKR','confidence':0.4,'bounds':[0,0,1,1]}]}).encode())
        with patch('workflow.mixed_formats.subprocess.run',side_effect=fake_run):
            f=pdf(FIXTURE.read_bytes(),'low-confidence',ocr_helper=Path('/usr/bin/true'))
        self.assertEqual(f['pages'][0]['status'],'ocr-low-confidence-unreviewed')
        self.assertEqual(f['pages'][0]['original_extracted_text'],'')
        self.assertTrue(any(r['kind']=='pdf-ocr-region' for r in f['records']))
        self.assertTrue(all(not p.exists() for p in seen))
    def test_timeout_invalid_confidence_and_wrong_page_fail_explicitly(self):
        import subprocess
        scenarios=[subprocess.TimeoutExpired('helper',20),{'status':'ok','page':2,'text':'bad target','confidence':1}, {'status':'ok','page':1,'text':'bad confidence','confidence':float('nan')}, {'status':'ok','page':1,'text':'unsupported language','confidence':1,'language':'fr-FR'}]
        for scenario in scenarios:
            with self.subTest(scenario=str(scenario)):
                response=SimpleNamespace(returncode=0,stdout=json.dumps(scenario).encode()) if isinstance(scenario,dict) else None
                options={'side_effect':scenario} if isinstance(scenario,Exception) else {'return_value':response}
                with patch('workflow.mixed_formats.subprocess.run',**options):
                    f=pdf(FIXTURE.read_bytes(),'failed-helper',ocr_helper=Path('/usr/bin/true'))
                self.assertEqual(len(f['pages']),1);self.assertEqual(f['pages'][0]['status'],'unreadable-scanned-page');self.assertTrue(f['parse_issues']);self.assertFalse(f['pages'][0]['text'])
    @unittest.skipUnless(native_ocr_helper() is not None,'Native local Vision/PDFKit helper has not been built')
    def test_actual_english_scanned_pdf_local_ocr(self):
        f=pdf(FIXTURE.read_bytes(),'real-local-ocr')
        self.assertEqual(f['page_count'],1);page=f['pages'][0]
        self.assertIn(page['status'],('ocr-extracted-unreviewed','ocr-low-confidence-unreviewed'))
        recognized=page['text'].casefold()
        for phrase in ('synthetic research paper','125','lkr','2026','100','patients'):self.assertIn(phrase,recognized)
        self.assertTrue(page['ocr']['regions']);self.assertGreaterEqual(page['ocr']['confidence'],0)
        self.assertEqual(page['ocr']['review_status'],'unreviewed; verify recognized values and scientific meaning')
        # Every recognized region and page survives graph, coverage and chunks.
        project=source_scope_draft(intake([FIXTURE]));build_chunk_ledger(project);self.assertTrue(validate_graph(project))
        ids=Counter(x for c in project['provenance']['chunks']['chunks'] for x in c['source_ids'])
        self.assertEqual(ids,Counter(source_items(project['provenance']['files'][0])))

if __name__=='__main__':unittest.main()
