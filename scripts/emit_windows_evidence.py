"""Publish reproducibility metadata in bounded log chunks, without app/user data."""
from pathlib import Path
import base64,gzip,json,re
ROOT=Path(__file__).resolve().parents[1]
report={'checks':json.loads((ROOT/'evidence/windows-checks.json').read_text()),'package':json.loads((ROOT/'evidence/windows-package-verification.json').read_text()),'build':json.loads((ROOT/'build/windows-build-manifest.json').read_text())}
report['failure_logs']={k:(ROOT/'evidence'/v['log']).read_text(encoding='utf-8',errors='replace') for k,v in report['checks'].items() if v['exit_code'] and 'log' in v}
report['test_summaries']={k:re.findall(r'(?:Ran \d+ tests?[^\n]*|^OK[^\n]*|^FAILED[^\n]*|^.+? \.\.\. skipped [^\n]*)',(ROOT/'evidence'/v['log']).read_text(encoding='utf-8',errors='replace'),re.M) for k,v in report['checks'].items() if 'log' in v}
raw=base64.b64encode(gzip.compress(json.dumps(report,sort_keys=True).encode())).decode();chunks=[raw[i:i+7000] for i in range(0,len(raw),7000)]
for i,chunk in enumerate(chunks):print('AMUA_WINDOWS_EVIDENCE '+str(i)+'/'+str(len(chunks))+' '+chunk)
