package v21;
import gui.frmMain;
import java.awt.*;
import java.nio.file.*;
import java.util.*;
import javax.swing.*;
public class GoogleAccountsCheck {
 static WorkflowPanel ui;static frmMain app;static Path capture;
 static void check(boolean yes,String why){if(!yes)throw new AssertionError(why);}
 static Map<String,Object> data(boolean signed){Map<String,Object> p=new LinkedHashMap<>();p.put("registration","google_synthetic");p.put("label","Google connection 1");p.put("signed_in",signed);p.put("active",signed);Map<String,Object> d=new LinkedHashMap<>();d.put("provider","gemini");d.put("accounts",Arrays.asList(p));return d;}
 static JButton button(Container parent,String text){for(Component c:parent.getComponents()){if(c instanceof JButton&&text.equals(((JButton)c).getText()))return (JButton)c;if(c instanceof Container){JButton b=button((Container)c,text);if(b!=null)return b;}}return null;}
 static void click(String label,boolean signed)throws Exception{Files.deleteIfExists(capture);SwingUtilities.invokeAndWait(()->{ui.chooseAccount(data(signed));for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()&&"Google accounts for Gemini".equals(((JDialog)w).getTitle())){JButton b=button((Container)w,label);check(b!=null,"Missing Google action "+label);b.doClick();return;}throw new AssertionError("Google picker absent");});}
 static String request()throws Exception{for(int i=0;i<100&&!Files.exists(capture);i++)Thread.sleep(20);check(Files.exists(capture),"No helper command");String r=new String(Files.readAllBytes(capture),"UTF-8");check(r.contains("\"provider\": \"gemini\""),"Wrong provider");Thread.sleep(150);return r;}
 public static void main(String[] args)throws Exception{try{
  Map<String,Object> progress=new LinkedHashMap<>();progress.put("event","auth_progress");progress.put("provider","gemini");progress.put("message","Finish Google sign-in in your browser.");check(WorkflowPanel.progressLabel(progress).contains("Google"),"Google progress mislabeled");
  capture=Paths.get(args[0]);SwingUtilities.invokeAndWait(()->{app=new frmMain("0.3.6");WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setVisible(true);ui.providerChoice.setSelectedIndex(1);});Thread.sleep(700);
  Files.deleteIfExists(capture);SwingUtilities.invokeAndWait(()->button(ui,"Connect account…").doClick());check(request().contains("\"action\": \"accounts\""),"Connect bypasses Google accounts");
  click("Add another Google account",true);String r=request();check(r.contains("\"mode\": \"add\"")&&!r.contains("\"account\""),"Add reused an account");
  click("Sign in again to selected connection",false);r=request();check(r.contains("\"mode\": \"reauthorize\"")&&r.contains("google_synthetic"),"Reconnect wrong account");
  click("Use selected connection",true);check(request().contains("\"action\": \"switch\""),"Saved account did not switch");
  click("Use selected connection",false);check(request().contains("\"mode\": \"reauthorize\""),"Disconnected Use did not reconnect");
  System.out.println("PASS Google account Swing UI with real helper subprocess capture: Connect opens Accounts, Google-specific picker, Add fresh, reconnect selected, switch saved, disconnected Use reauthorizes; no real authentication");System.exit(0);
 }catch(Throwable e){e.printStackTrace();System.exit(1);}}
}
