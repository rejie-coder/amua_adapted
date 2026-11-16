"""Bounded app-owned Windows PDF/English OCR using OS WinRT components."""
from pathlib import Path
import argparse,base64,json,os,subprocess,sys

def main():
 p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True);group.add_argument('--pdf');group.add_argument('--stdin',action='store_true');p.add_argument('--page',type=int,required=True);p.add_argument('--max-pixels',type=int,default=8000000);a=p.parse_args()
 result={'status':'unsupported','reason_category':'windows-ocr-unavailable','language':'en-US','page':a.page}
 try:
  if os.name!='nt' or not 1<=a.page or not 1<=a.max_pixels<=8000000:raise ValueError()
  if a.stdin:data=sys.stdin.buffer.read(25*1024*1024+1)
  else:
   source=Path(a.pdf)
   if not source.is_absolute() or not source.is_file() or source.stat().st_size>25*1024*1024:raise ValueError()
   data=source.read_bytes()
  if len(data)>25*1024*1024:raise ValueError()
  script=Path(__file__).with_name('windows-ocr.ps1').read_text(encoding='utf-8');encoded=base64.b64encode(script.encode('utf-16-le')).decode()
  environment=dict(os.environ,AMUA_OCR_PAGE=str(a.page),AMUA_OCR_PIXELS=str(a.max_pixels))
  powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
  completed=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],input=base64.b64encode(data),capture_output=True,timeout=16,env=environment,creationflags=subprocess.CREATE_NO_WINDOW)
  if len(completed.stdout)>4*1024*1024:raise ValueError()
  result=json.loads(completed.stdout.decode('utf-8-sig'))
 except subprocess.TimeoutExpired:result['reason_category']='windows-ocr-timeout'
 except Exception:pass
 print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
