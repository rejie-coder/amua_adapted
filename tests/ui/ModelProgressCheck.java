package v21;
import javax.swing.*;
import java.nio.file.*;
import java.util.*;

/** Actual sidebar timer/control state with clock offsets; no minute-long sleeps. */
public class ModelProgressCheck {
 static void require(boolean value,String why){if(!value)throw new AssertionError(why);}
 static Map<String,Object> progress(long sequence,boolean meaningful){Map<String,Object> p=new LinkedHashMap<>();p.put("event","model_progress");p.put("progress_sequence",sequence);p.put("meaningful",meaningful);p.put("phase","receiving");p.put("characters",12);return p;}
 public static void main(String[] args)throws Exception{
  SwingUtilities.invokeAndWait(()->{try{
   gui.frmMain app=ModelChatControllerCheck.host();String xml=new String(Files.readAllBytes(Paths.get(args[0])),java.nio.charset.StandardCharsets.UTF_8);ModelChat.apply(app,xml,null,null,false);
   base.AmuaModel model=(base.AmuaModel)ModelChatControllerCheck.get(app,"curModel");String before=(String)WorkspaceSnapshot.capture(model).get("sha256");
   WorkflowPanel ui=new WorkflowPanel(app);ui.stop();ui.preferences.putInt("model_chat_idle_seconds",180);Map<String,Object> req=ui.req("chat-request");req.put("idle_timeout_seconds",180);ui.activeAction="chat-request";ui.beginActivity("provider",req);
   long token=ui.epoch.get();ui.activityStarted=System.nanoTime()-900000000000L;ui.lastModelProgressNanos=System.nanoTime()-2000000000L;ui.updateActivity();
   require(ui.activityTimer.isRunning()&&ui.epoch.get()==token,"A progressing15-minute stream was stopped by total elapsed time");
   ui.provider("status");require(ui.epoch.get()==token&&ui.activityTimer.isRunning(),"Status cancelled the active AI request");
   ui.lastModelProgressNanos=System.nanoTime()-170000000000L;ui.acceptModelProgress(progress(1,true),token);long recent=ui.lastModelProgressNanos;require(System.nanoTime()-recent<1000000000L,"Meaningful progress did not reset idle clock");
   ui.acceptModelProgress(progress(2,true),token-1);require(ui.lastModelProgressNanos==recent,"Late reply from old operation extended timeout");
   ui.acceptModelProgress(progress(1,true),token);require(ui.lastModelProgressNanos==recent,"Duplicate progress extended timeout");
   ui.acceptModelProgress(progress(3,false),token);require(ui.lastModelProgressNanos==recent,"Keepalive extended timeout");
   ui.lastModelProgressNanos=System.nanoTime()-181000000000L;ui.updateActivity();require(!ui.activityTimer.isRunning()&&ui.process==null&&ui.epoch.get()>token,"Stalled operation did not stop");require(ui.conversation.getText().contains("No meaningful AI"),"Stall was not explained");
   require(WorkspaceSnapshot.capture(model).get("sha256").equals(before),"Stall changed model");
   ui.preferences.putInt("model_chat_idle_seconds",600);req.put("idle_timeout_seconds",600);ui.beginActivity("provider",req);ui.activityStarted=System.nanoTime()-1800000000000L;ui.lastModelProgressNanos=System.nanoTime()-300000000000L;ui.updateActivity();require(ui.activityTimer.isRunning(),"User-selected10-minute idle window was ignored");ui.stop();
   require(!ui.activityTimer.isRunning()&&ui.process==null,"Stop failed");require(WorkspaceSnapshot.capture(model).get("sha256").equals(before),"Stop changed model");
   System.out.println("PASS real sidebar:15-minute progressing response allowed, fresh progress extends wait, duplicate/stale/keepalive ignored, idle stall stops, custom10-minute idle window, noncancelling Status, Stop and unchanged editable model");System.exit(0);
  }catch(Throwable error){error.printStackTrace();System.exit(1);}});
 }
}
