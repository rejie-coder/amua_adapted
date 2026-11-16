from pathlib import Path
import json,subprocess,sys
r=Path(__file__).resolve().parents[2];result=subprocess.run([str(r/'Amua/Resources/python/python.exe'),str(r/'Amua/Resources/libexec/amua-ocr.py'),'--pdf',str(r/'tests/workflow/fixtures/synthetic-scanned-english.pdf'),'--page','1'],capture_output=True,text=True,encoding='utf-8',timeout=25)
print(result.stdout);(r/'evidence/windows-ocr-result.json').write_text(result.stdout,encoding='utf-8')
