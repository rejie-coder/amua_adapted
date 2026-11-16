"""Assert privacy using the host's real permission model rather than fake POSIX bits."""
from pathlib import Path
import base64,json,os,stat,subprocess

def assert_private_file(case,path):
 path=Path(path)
 if os.name!='nt':case.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600);return
 script="""$ErrorActionPreference='Stop';$acl=[System.IO.File]::GetAccessControl($env:AMUA_ACL_TEST_PATH);$bad=@();foreach($rule in $acl.Access){$sid=$rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;if($rule.AccessControlType -eq 'Allow' -and $sid -in @('S-1-1-0','S-1-5-11','S-1-5-32-545') -and (([int]$rule.FileSystemRights -band 852246) -ne 0)){$bad+=$sid}};@{safe=($bad.Count -eq 0);broad_writers=$bad}|ConvertTo-Json -Compress"""
 powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe';environment={**os.environ,'AMUA_ACL_TEST_PATH':str(path.resolve())}
 r=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],env=environment,capture_output=True,text=True,encoding='utf-8',timeout=10)
 case.assertEqual(r.returncode,0,r.stderr);case.assertTrue(json.loads(r.stdout)['safe'],'Private file grants broad Windows write access')
