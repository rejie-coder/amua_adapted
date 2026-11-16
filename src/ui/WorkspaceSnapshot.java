package v21;
import base.AmuaModel;
import javax.swing.SwingUtilities;
import javax.xml.bind.*;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
/** Read-only consistent legacy-model snapshot for reviewed AI suggestions. */
public final class WorkspaceSnapshot {
 public static Map<String,Object> capture(AmuaModel model){
  if(!SwingUtilities.isEventDispatchThread())throw new IllegalStateException("Capture the workspace on the event thread");
  if(model==null)return null;
  try{
   Marshaller m=JAXBContext.newInstance(AmuaModel.class).createMarshaller();m.setProperty(Marshaller.JAXB_ENCODING,"UTF-8");
   StringWriter out=new StringWriter();m.marshal(model,out);String xml=out.toString();
   byte[] bytes=xml.getBytes(StandardCharsets.UTF_8);if(bytes.length>24*1024*1024)throw new IllegalArgumentException("Workspace model needs a larger analysis batch; nothing was sent");
   byte[] hash=MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder h=new StringBuilder();for(byte b:hash)h.append(String.format("%02x",b&255));
   Map<String,Object> result=new LinkedHashMap<>();result.put("format","amua-legacy-xml-v1");result.put("name",model.name==null?"Untitled model":model.name);result.put("model_type",model.type==0?"decision_tree":"markov");result.put("node_count",model.type==0?model.tree.nodes.size():model.markov.nodes.size());result.put("sha256",h.toString());result.put("xml",xml);result.put("runtime_results_included",false);result.put("review_scope","Consistent read-only snapshot for a reviewed native proposal or original-engine analysis. Bind application to sha256; never mutate this snapshot.");return result;
  }catch(RuntimeException e){throw e;}catch(Exception e){throw new IllegalStateException("The workspace could not be prepared for review",e);}
 }
}
