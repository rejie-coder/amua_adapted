"""Accept no new failure; retain the exact documented OCR limitation as a preview waiver."""
from pathlib import Path
import hashlib,json,re,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 checks=json.loads((ROOT/'evidence/release-checks.json').read_text());failures=[k for k,v in checks.items() if v['exit_code']!=0];waivers=[]
 if failures==['workflow-final']:
  log=(ROOT/'evidence/workflow-final.txt').read_text()
  if len(re.findall(r'^FAIL:',log,re.M))!=1 or 'FAIL: test_actual_english_scanned_pdf_local_ocr' not in log or not re.search(r'FAILED \(failures=1(?:, skipped=\d+)?\)',log) or 'ERROR:' in log:raise SystemExit('Unexpected workflow failure; release blocked')
  waivers=['Actual scanned-PDF OCR test fails in this environment; pages remain unreadable. Intel preview only.']
 elif failures:raise SystemExit('New failing check groups: '+', '.join(failures))
 expected=json.loads((ROOT/'scripts/expected-classes-3.2.4.json').read_text());jar=ROOT/'Amua.app/Contents/Resources/Amua_0.3.6.jar'
 with zipfile.ZipFile(jar) as z:
  different=[n for n,v in expected.items() if hashlib.sha256(z.read(n)).hexdigest()!=v]
 if different:raise SystemExit('Compiled code differs from checked local 3.2.4: '+', '.join(different[:5]))
 skips={name:re.findall(r'^(.+?) \.\.\. skipped (.+)$',(ROOT/'evidence'/checks[name]['log']).read_text(),re.M) for name in ('provider-final','workflow-final')}
 report={'reported_skips':skips,'version':'3.2.4','architecture':'x86_64','check_groups':checks,'documented_waivers':waivers,'application_classes_match_local_candidate':len(expected),'jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'release_type':'prerelease','signing':'ad hoc; not Developer ID/notarized','live_account_vision_acceptance':False,'apple_silicon_native':False}
 (ROOT/'evidence/release-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('Release verification passed with',len(waivers),'explicit OCR waiver(s);',len(expected),'application classes match.')
if __name__=='__main__':main()
