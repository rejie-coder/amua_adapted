"""No account or inference: real bundled CLI initialization in an isolated profile."""
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Amua/Resources'))
from gemini_acp import ACP,runtime
class RuntimeTests(unittest.TestCase):
 def test_bundled_official_protocol_and_google_auth(self):
  with tempfile.TemporaryDirectory() as d:
   c=ACP(runtime(),Path(d),timeout=45)
   try:
    self.assertEqual(c.info['protocolVersion'],1)
    self.assertEqual(c.info['agentInfo']['version'],'0.68.0')
    self.assertIn('oauth-personal',[a['id'] for a in c.info['authMethods']])
   finally:c.close()
if __name__=='__main__':unittest.main()
