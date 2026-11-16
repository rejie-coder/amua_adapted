"""Pinned official Google CLI and Node runtime, verified before extraction."""
from pathlib import Path
import shutil
from bootstrap_windows import ROOT, TOOLS, get, unpack
CLI={'url':'https://registry.npmjs.org/@google/gemini-cli/-/gemini-cli-0.68.0.tgz','sha256':'325099ddcb56937c27d119e7297bfa8a5e29b529bae3c92fdf3b71a36d5fa006'}
NODE={'url':'https://nodejs.org/dist/v24.11.1/node-v24.11.1-win-x64.zip','sha256':'5355ae6d7c49eddcfde7d34ac3486820600a831bf81dc3bdca5c8db6a9bb0e76'}
def main():
 for spec,name in [(CLI,'gemini-0.68.0.tgz'),(NODE,'node-24.11.1.zip')]:
  path=ROOT/'build/downloads'/name;get(spec,path);unpack(path)
 target=TOOLS/'gemini';target.mkdir(exist_ok=True)
 shutil.copy2(TOOLS/'node-v24.11.1-win-x64/node.exe',target/'node.exe')
 shutil.copy2(TOOLS/'node-v24.11.1-win-x64/LICENSE',target/'NODE-LICENSE.txt')
 shutil.copytree(TOOLS/'package',target/'package',dirs_exist_ok=True)
 print('Pinned Gemini CLI 0.68.0 and Node 24.11.1 ready')
if __name__=='__main__':main()
