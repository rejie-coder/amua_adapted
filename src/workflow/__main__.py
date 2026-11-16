import json
import sys
from .core import intake, d2p_draft, summary, open_project
if sys.argv[1]=='intake':
    p=intake(sys.argv[2:]);print(json.dumps({'project':p,'summary':summary(p)},indent=2))
elif sys.argv[1]=='inspect-project':
    p=open_project(sys.argv[2]);print(json.dumps({'project':p,'summary':summary(p)},indent=2))
else:raise SystemExit('Use intake <paths> or inspect-project <path>')
