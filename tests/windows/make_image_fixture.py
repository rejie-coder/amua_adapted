from pathlib import Path
import json,sys,tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Amua/Resources'),str(ROOT/'Amua/Resources/pythonlib'),str(ROOT/'tests/provider')]
from test_image_chat import image_chat
import model_chat as mc
folder=ROOT/'evidence/image-chat';folder.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as support:preview,response,_=image_chat(support)
(folder/'preview.json').write_text(json.dumps(preview),encoding='utf-8');(folder/'proposal-response.json').write_text(json.dumps(response),encoding='utf-8')
e=mc.context(None,{'xml':response['candidate_xml'],'sha256':'synthetic'});p=mc.local_answer('approve structure',e);e=mc.context(None,{'xml':mc.xml_for(p,e),'sha256':'synthetic'});p=mc.local_answer('approve inputs',e);confirmed=mc.response(p,e);confirmed['local_answer']=True
(folder/'confirmed-response.json').write_text(json.dumps(confirmed),encoding='utf-8');(folder/'reviewed.amua').write_text(confirmed['candidate_xml'],encoding='utf-8')
