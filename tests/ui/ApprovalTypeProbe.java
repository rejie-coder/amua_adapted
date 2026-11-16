import javax.script.*;
import java.util.*;
import v21.WorkflowPanel;
public class ApprovalTypeProbe {
 public static void main(String[] args)throws Exception{
  ScriptEngine e=new ScriptEngineManager().getEngineByName("nashorn");
  for(int count:new int[]{1,4,28}){
   e.put("payload","{\"required_calls\":"+count+"}");Map m=(Map)e.eval("Java.asJSONCompatible(JSON.parse(payload))");Object n=m.get("required_calls");Map r=new LinkedHashMap();r.put("approved_max_calls",n);System.out.println(n.getClass().getName()+" "+WorkflowPanel.json(r));
  }
 }
}
