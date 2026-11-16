"""Publish reproducibility metadata in bounded log chunks, without app/user data."""
from pathlib import Path
import base64,gzip,json
ROOT=Path(__file__).resolve().parents[1]
report={'checks':json.loads((ROOT/'evidence/windows-checks.json').read_text()),'package':json.loads((ROOT/'evidence/windows-package-verification.json').read_text()),'build':json.loads((ROOT/'build/windows-build-manifest.json').read_text())}
raw=base64.b64encode(gzip.compress(json.dumps(report,sort_keys=True).encode())).decode();chunks=[raw[i:i+7000] for i in range(0,len(raw),7000)]
for i,chunk in enumerate(chunks):print('AMUA_WINDOWS_EVIDENCE '+str(i)+'/'+str(len(chunks))+' '+chunk)
