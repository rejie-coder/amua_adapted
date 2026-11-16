"""Image -> actual provider-helper dispatch -> guarded proposal -> original engine.

Remote vision output is a fixture. Input preparation, validation, review answers,
XML conversion, Java validation/calculation and saved artifacts are production.
"""
import json,sys,tempfile,subprocess,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RES=ROOT/'Amua.app/Contents/Resources'
sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src'),str(ROOT/'tests/provider')]
import model_chat as mc
from test_image_chat import image_chat

def engine(path,folder):
    command=folder/'engine-command.json';command.write_text('{"operation":"run"}')
    result=subprocess.run([str(RES/'runtime/bin/java'),'-Djava.awt.headless=true','-Djava.util.prefs.userRoot='+str(folder/'prefs'),'-cp',str(RES/'Amua_0.3.6.jar'),'v21.ChatEngine',str(path),str(command)],capture_output=True,text=True,timeout=20)
    return json.loads(result.stdout.strip().splitlines()[-1])

def main():
    folder=ROOT/'evidence/image-chat';folder.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'build') as support:preview,response,broker=image_chat(support)
    (folder/'preview.json').write_text(json.dumps(preview,indent=2)+'\n')
    (folder/'proposal-response.json').write_text(json.dumps(response,indent=2)+'\n')
    draft=folder/'preliminary.amua';draft.write_text(preview['draft_xml'])
    proposed=folder/'image-proposal.amua';proposed.write_text(response['candidate_xml'])
    blocked=engine(proposed,folder);assert not blocked['ok'],'Unreviewed image values must not calculate'
    evidence=mc.context(None,{'xml':response['candidate_xml'],'sha256':'synthetic'})
    structure=mc.local_answer('approve structure',evidence);assert any(q['field']=='input_review' for q in structure['questions'])
    evidence=mc.context(None,{'xml':mc.xml_for(structure,evidence),'sha256':'synthetic'})
    inputs=mc.local_answer('approve inputs',evidence);confirmed=mc.response(inputs,evidence);confirmed['local_answer']=True
    (folder/'confirmed-response.json').write_text(json.dumps(confirmed,indent=2)+'\n')
    model=folder/'Drug A vs Drug B - reviewed test fixture.amua';model.write_text(confirmed['candidate_xml'])
    calculation=engine(model,folder);assert calculation['ok'],calculation
    expected=json.loads((ROOT/'tests/provider/fixtures/drug-table-expected.json').read_text())
    for row in calculation['results']:assert math.isclose(row['value'],expected[row['strategy']][row['outcome']],rel_tol=1e-12),row
    actual={r['strategy']+'|'+r['outcome']:r['value'] for r in calculation['results']}
    icer=(actual['Drug B|Cost ($)']-actual['Drug A|Cost ($)'])/(actual['Drug B|Effectiveness (QALYs)']-actual['Drug A|Effectiveness (QALYs)'])
    assert math.isclose(icer,1030.76923076923,rel_tol=1e-12)
    report={'remote_response':'synthetic fixture; not live account/vision acceptance','image_sent_to_provider':broker.calls,'proposal_nodes':len(response['proposal']['model']['nodes']),
            'question_bindings_retained':response['proposal']['question_binding_warnings'],'unreviewed_calculation_blocked':not blocked['ok'],
            'explicit_synthetic_reviews':['approve structure','approve inputs'],'original_engine_results':calculation['results'],'incremental_icer':icer}
    (folder/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
