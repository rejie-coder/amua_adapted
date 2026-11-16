package v21;
import javax.swing.*;
import java.nio.file.*;
import java.util.*;

/** Real helper subprocess -> JSON-lines -> sidebar progress/timer, synthetic service. */
public class ModelProgressWireCheck {
 static WorkflowPanel ui;
 static void require(boolean condition,String why){if(!condition)throw new AssertionError(why);}
 public static void main(String[] args)throws Exception{
  SwingUtilities.invokeAndWait(()->{try{
   gui.frmMain app=ModelChatControllerCheck.host();ui=new WorkflowPanel(app);ui.stop();Map<String,Object> r=ui.req("chat-request");r.put("text","synthetic-wire");r.put("idle_timeout_seconds",180);ui.invoke("provider",r);
  }catch(Exception error){throw new RuntimeException(error);}});
  boolean sawProgress=false;
  for(int i=0;i<100;i++){
   final boolean[] ready={false};SwingUtilities.invokeAndWait(()->{ready[0]=ui.lastModelProgressSequence>=2&&ui.activityTimer.isRunning();if(ready[0]){ui.activityStarted=System.nanoTime()-900000000000L;ui.updateActivity();require(ui.activityTimer.isRunning(),"Real wire progress was stopped by old total cutoff");}});
   if(ready[0]){sawProgress=true;break;}Thread.sleep(20);
  }
  require(sawProgress,"No progress crossed the real helper pipe");
  for(int i=0;i<100;i++){final boolean[] idle={false};SwingUtilities.invokeAndWait(()->idle[0]=!ui.activityTimer.isRunning());if(idle[0])break;Thread.sleep(20);}
  SwingUtilities.invokeAndWait(()->{
   require(ui.lastModelProgressSequence==8,"Progress sequence lost or truncated");require(ui.conversation.getText().contains("ChatGPT: synthetic-wire-complete"),"Final reply absent");require(!ui.activityTimer.isRunning()&&ui.process==null,"Completed operation remained active");
   Map<String,Object> r=ui.req("chat-request");r.put("text","cancelled-wire");r.put("idle_timeout_seconds",180);ui.invoke("provider",r);ui.stop();
  });
  Thread.sleep(700);
  SwingUtilities.invokeAndWait(()->{require(!ui.activityTimer.isRunning()&&ui.process==null,"Late output restarted operation");require(ui.status.getText().startsWith("Stopped"),"Late output replaced Stop state");require(!ui.conversation.getText().contains("cancelled-wire-complete"),"Cancelled final reply was applied");System.out.println("PASS real helper subprocess/JSON-lines/sidebar: progress sequence crosses pipe,15-minute elapsed operation continues with progress, complete reply finishes, Stop discards late reply");System.exit(0);});
 }
}
