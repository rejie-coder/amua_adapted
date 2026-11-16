"""Numerical and native-state acceptance of the actual release JAR."""
import json,sys,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RES=ROOT/'Amua.app/Contents/Resources'
sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src')]
import model_chat as mc

def run_model(xml,directory,name):
    model=directory/(name+'.amua');model.write_text(xml);command=directory/'command.json';command.write_text('{"operation":"run"}')
    p=subprocess.run([str(RES/'runtime/bin/java'),'-Djava.awt.headless=true','-Djava.util.prefs.userRoot='+str(directory/'prefs'),'-cp',str(RES/'Amua_0.3.6.jar'),'v21.ChatEngine',str(model),str(command)],capture_output=True,text=True,timeout=20)
    data=json.loads(p.stdout.strip().splitlines()[-1]);assert data.get('ok'),data
    return data['results'][0]['value']

def main():
    result={}
    with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
        directory=Path(temp);before=(ROOT/'tests/hardening/fixtures/variable-updates.amua').read_text()
        evidence=mc.context(None,{'xml':before,'sha256':'synthetic'})
        after=mc.xml_for(mc.local_answer('approve structure',evidence),evidence)
        result['approval_preserves_variable_update']={'before':run_model(before,directory,'before'),'after':run_model(after,directory,'after')}
        assert result['approval_preserves_variable_update']=={'before':5.0,'after':5.0}
        root=ET.fromstring(before);ET.SubElement(root,'Variable').extend([ET.Element('name'),ET.Element('expression')]);root.findall('Variable')[-1].find('name').text='dependent';root.findall('Variable')[-1].find('expression').text='x*2'
        leaf=root.findall('tree/Node')[1];leaf.find('payoff').text='dependent'
        original=ET.tostring(root,encoding='unicode');evidence=mc.context(None,{'xml':original,'sha256':'synthetic'})
        edited=mc.xml_for(mc.local_answer('approve structure',evidence),evidence)
        result['dependent_variable_preserved']={'before':run_model(original,directory,'dependent-before'),'after':run_model(edited,directory,'dependent-after')}
        assert result['dependent_variable_preserved']=={'before':10.0,'after':10.0}
        # A value answer updates only its intended outcome, preserving node updates.
        plan=mc.saved_state(before)['proposal'];plan['questions']=[{'id':'Q1','text':'Outcome','node':'a','field':'payoff','dimension':0}]
        notes=root.findall('tree/Node')[0].find('notes');notes.text=notes.text.split(mc.MARKER)[0]+mc.MARKER+mc.packed({'proposal':plan,'evidence':{}})
        original=ET.tostring(root,encoding='unicode');evidence=mc.context(None,{'xml':original,'sha256':'synthetic'})
        answered=mc.xml_for(mc.local_answer('Q1 = x+1',evidence),evidence)
        value=run_model(answered,directory,'answer');assert value==6.0,value
        result['targeted_answer_keeps_update']=value
        # Native fields outside the chat representation survive the conversion.
        original_root=ET.fromstring(before);node=original_root.findall('tree/Node')[1];ET.SubElement(node,'syntheticFutureField').text='preserved'
        evidence=mc.context(None,{'xml':ET.tostring(original_root,encoding='unicode'),'sha256':'synthetic'})
        converted=ET.fromstring(mc.xml_for(mc.local_answer('approve structure',evidence),evidence))
        assert converted.findtext('tree/Node[2]/syntheticFutureField')=='preserved'
        result['unknown_native_field_preserved']=True
    (ROOT/'evidence/hardening-engine.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
