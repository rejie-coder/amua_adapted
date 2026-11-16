package v21;
import javax.script.*;
import java.util.*;
public class ApprovalPlanCheck {
 static Map<String,Object> parse(String value)throws Exception{ScriptEngine e=new ScriptEngineManager().getEngineByName("nashorn");e.put("payload",value);return (Map<String,Object>)e.eval("Java.asJSONCompatible(JSON.parse(payload))");}
 public static void main(String[] args)throws Exception{
  for(int count:new int[]{0,1,29,32,43,129}){
   Map<String,Object> preview=parse("{\"required_calls\":"+count+",\"remaining_calls\":null,\"session_call_limit\":null,\"calls_used\":200,\"transport_hash\":\"testhash\"}");
   Map result=WorkflowPanel.approvedRequest(new LinkedHashMap<>(),preview);
   if(!(result.get("approved_max_calls") instanceof Integer)||!Integer.valueOf(count).equals(result.get("approved_max_calls"))||!"testhash".equals(result.get("approved_transport_hash")))throw new AssertionError("Malformed approved payload");
  }
  for(String preview:new String[]{"{\"required_calls\":-1}","{\"required_calls\":1.5}","{\"required_calls\":true}","{\"required_calls\":1,\"can_send\":false}","{\"required_calls\":1,\"feasible\":false}"}){
   try{WorkflowPanel.approvedRequest(new LinkedHashMap<>(),parse(preview));throw new AssertionError("Invalid approval accepted");}catch(IllegalArgumentException expected){}
  }
  System.out.println("PASS Nashorn request approval with no session cap: 29/43/129 calls after200 prior calls; exact integer and transport binding; invalid/unready requests rejected");
 }
}
