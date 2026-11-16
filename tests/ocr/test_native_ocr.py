import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src/dependencies/python'))
from pypdf import PdfWriter,PdfReader
BIN=Path(os.environ.get('AMUA_OCR_BINARY',str(R/'build/tools/amua-ocr'))).resolve()
SCAN=R/'tests/workflow/fixtures/synthetic-scanned-english.pdf'
class NativeOCR(unittest.TestCase):
 def call(self,path,page=1,pixels=8000000):
  p=subprocess.run([str(BIN),'--pdf',str(path),'--page',str(page),'--max-pixels',str(pixels)],capture_output=True,text=True,timeout=20)
  self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stderr,'');self.assertNotIn(str(path),p.stdout);return json.loads(p.stdout)
 def test_real_image_only_research_page_offline(self):
  self.assertFalse((PdfReader(SCAN).pages[0].extract_text() or '').strip())
  value=self.call(SCAN);self.assertEqual(value['status'],'ok');self.assertEqual(value['review_status'],'unreviewed_ocr')
  for text in ('SYNTHETIC RESEARCH PAPER','125','LKR','2026','100','patients'):self.assertIn(text,value['text'])
  self.assertGreater(len(value['regions']),0);self.assertTrue(0<=value['confidence']<=1);self.assertLessEqual(value['raster']['width']*value['raster']['height'],8000000)
 def test_blank_page_explicitly_unreadable(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td).resolve()/'blank.pdf';w=PdfWriter();w.add_blank_page(width=612,height=792);w.write(str(p));v=self.call(p);self.assertEqual(v['status'],'unreadable');self.assertEqual(v['reason_category'],'empty')
 def test_encrypted_pdf_explicitly_unsupported(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td).resolve()/'encrypted.pdf';w=PdfWriter();w.append(str(SCAN));w.encrypt('synthetic-password');w.write(str(p));v=self.call(p);self.assertEqual(v['status'],'unsupported');self.assertEqual(v['reason_category'],'encrypted')
 def test_invalid_input_and_page_boundaries(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td).resolve()/'bad.pdf';p.write_bytes(b'not a PDF');self.assertEqual(self.call(p)['reason_category'],'invalid_pdf');self.assertEqual(self.call(p.parent/'missing.pdf')['status'],'unsupported')
  self.assertEqual(self.call(SCAN,page=0)['reason_category'],'invalid_arguments');self.assertEqual(self.call(SCAN,page=2)['reason_category'],'page_out_of_range')
 def test_pixel_and_file_size_limits(self):
  self.assertEqual(self.call(SCAN,pixels=8000001)['reason_category'],'invalid_arguments')
  low=self.call(SCAN,pixels=100000)
  if low['status']=='ok':self.assertLessEqual(low['raster']['width']*low['raster']['height'],100000)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td).resolve()/'large.pdf'
   with p.open('wb') as f:f.truncate(25*1024*1024+1)
   self.assertEqual(self.call(p)['reason_category'],'input_limit_or_type')
 def test_symlink_input_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td).resolve()/'link.pdf';p.symlink_to(SCAN);self.assertEqual(self.call(p)['reason_category'],'input_unavailable')
 def test_parent_death_terminates_helper_within_two_seconds(self):
  code="import subprocess,sys,time;p=subprocess.Popen(sys.argv[1:],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);print(p.pid,flush=True);time.sleep(30)"
  parent=subprocess.Popen([sys.executable,'-c',code,str(BIN),'--pdf',str(SCAN),'--page','1','--max-pixels','8000000'],stdout=subprocess.PIPE,text=True)
  try:
   pid=int(parent.stdout.readline());os.kill(pid,0);started=time.monotonic();parent.kill();parent.wait(timeout=3)
   while time.monotonic()-started<2:
    status=subprocess.run(['/bin/ps','-p',str(pid),'-o','stat='],text=True,capture_output=True).stdout.strip()
    if not status or status.startswith('Z'):break
    time.sleep(.05)
   else:self.fail('OCR child survived parent death for2seconds')
   print('parent_death_exit_ms='+str(round((time.monotonic()-started)*1000)))
  finally:
   if parent.poll() is None:parent.kill();parent.wait(timeout=3)
   parent.stdout.close()
if __name__=='__main__':unittest.main()
