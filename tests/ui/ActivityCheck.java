package v21;
import gui.frmMain;
import javax.swing.*;
import java.util.*;
public class ActivityCheck {
 static WorkflowPanel ui;
 static void check(boolean b,String why){if(!b)throw new AssertionError(why);}
 static void start(String action,String text)throws Exception{SwingUtilities.invokeAndWait(()->{Map<String,Object> r=ui.req(action);r.put("text",text);ui.invoke("provider",r);check(ui.activity.isIndeterminate()&&ui.activity.isShowing()&&ui.activityTimer.isRunning(),"No animated busy indicator");});}
 static void idle()throws Exception{for(int i=0;i<100;i++){final boolean[] b={false};SwingUtilities.invokeAndWait(()->b[0]=!ui.activityTimer.isRunning());if(b[0])return;Thread.sleep(50);}throw new AssertionError("Activity did not stop");}
 public static void main(String[] args)throws Exception{try{
 SwingUtilities.invokeAndWait(()->{frmMain app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setVisible(true);});
 start("request","slow");Thread.sleep(1100);SwingUtilities.invokeAndWait(()->{check(ui.activity.getString().contains("1s"),"Elapsed time not advancing");check(ui.status.getText().contains("Waiting for ChatGPT"),"Unclear request state");});idle();
 SwingUtilities.invokeAndWait(()->check(!ui.activity.isVisible()&&!ui.activity.isIndeterminate(),"Completion left activity running"));
 start("status","error");idle();SwingUtilities.invokeAndWait(()->check(ui.status.getText().equals("Needs attention"),"Error state hidden"));
 start("connect","slow");SwingUtilities.invokeAndWait(()->{check(ui.status.getText().contains("browser"),"Sign-in state unclear");ui.stop();check(!ui.activityTimer.isRunning()&&!ui.activity.isVisible(),"Stop left animation running");});Thread.sleep(1800);SwingUtilities.invokeAndWait(()->check(ui.status.getText().startsWith("Stopped"),"Late completion changed cancelled status"));
 start("status","slow");start("status","fast");idle();Thread.sleep(1700);SwingUtilities.invokeAndWait(()->check(!ui.activity.isVisible(),"Stale request restarted activity"));
 System.out.println("PASS actual Swing activity: visible animated indeterminate bar, elapsed seconds, request/browser labels; success/error/Stop/replacement stop activity and reject late state");System.exit(0);
 }catch(Throwable e){e.printStackTrace();System.exit(1);}}
}
