package v21;
import gui.frmMain;
import javax.swing.*;
import java.awt.*;
import java.nio.file.*;
import java.util.*;
import java.util.List;
public class AccountPickerCheck {
 static WorkflowPanel ui;static frmMain app;
 static void check(boolean b,String reason){if(!b)throw new AssertionError(reason);}
 static Component named(Container parent,String text){for(Component c:parent.getComponents()){if(c instanceof JButton&&text.equals(((JButton)c).getText()))return c;if(c instanceof Container){Component found=named((Container)c,text);if(found!=null)return found;}}return null;}
 static JList list(Container parent){for(Component c:parent.getComponents()){if(c instanceof JList)return (JList)c;if(c instanceof Container){JList found=list((Container)c);if(found!=null)return found;}}return null;}
 static Map<String,Object> profile(String id,String label,boolean active){Map<String,Object> p=new LinkedHashMap<>();p.put("registration",id);p.put("label",label);p.put("email","same@example.invalid");p.put("active",active);p.put("signed_in",true);p.put("plan_enabled",true);return p;}
 static void openAndClick(String action,int index)throws Exception{openAndClick(action,index,true);}
 static void openAndClick(String action,int index,boolean confirm)throws Exception{
  SwingUtilities.invokeAndWait(()->{Map<String,Object> d=new LinkedHashMap<>();List<Object> a=new ArrayList<>();a.add(profile("one","Personal · Connection 1",true));a.add(profile("two","Work · Connection 2",false));d.put("accounts",a);d.put("pending_attempts",new ArrayList<>());ui.chooseAccount(d);
   for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()&&"ChatGPT accounts and workspaces".equals(((JDialog)w).getTitle())){JList profiles=list((Container)w);check(profiles.getModel().getSize()==2,"same-email connections merged");check(!profiles.getModel().getElementAt(0).equals(profiles.getModel().getElementAt(1)),"labels not distinct");profiles.setSelectedIndex(index);if(action.startsWith("Remove")){javax.swing.Timer confirmTimer=new javax.swing.Timer(50,e->{for(Window modal:Window.getWindows())if(modal instanceof JDialog&&modal.isVisible()&&"Remove connection".equals(((JDialog)modal).getTitle())){JButton answer=(JButton)named((Container)modal,confirm?"OK":"Cancel");if(answer!=null)answer.doClick();}});confirmTimer.setRepeats(false);confirmTimer.start();}((JButton)named((Container)w,action)).doClick();return;}throw new AssertionError("Picker absent");});
 }
 public static void main(String[] args)throws Exception{
  try{
   Path capture=Paths.get(args[0]);SwingUtilities.invokeAndWait(()->{app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setVisible(true);});
   for(String action:new String[]{"Add another account or workspace","Sign in again to selected connection","Use selected connection","Remove selected connection"}){
    Files.deleteIfExists(capture);openAndClick(action,1);for(int i=0;i<100&&!Files.exists(capture);i++)Thread.sleep(50);check(Files.exists(capture),"No helper command");String payload=new String(Files.readAllBytes(capture),java.nio.charset.StandardCharsets.UTF_8);
    if(action.startsWith("Add"))check(payload.contains("\"mode\": \"add\"")&&!payload.contains("\"account\""),"Add reused a registration");
    else if(action.startsWith("Sign"))check(payload.contains("\"mode\": \"reauthorize\"")&&payload.contains("\"account\": \"two\""),"Reauth not selected registration");
    else if(action.startsWith("Remove"))check(payload.contains("\"action\": \"remove\"")&&payload.contains("\"account\": \"two\""),"Remove not selected registration");
    else check(payload.contains("\"action\": \"switch\"")&&payload.contains("\"account\": \"two\""),"Switch not selected registration");
    Thread.sleep(200);
   }
   Files.deleteIfExists(capture);openAndClick("Remove selected connection",0,false);Thread.sleep(200);check(!Files.exists(capture),"Cancelled removal sent helper command");
   SwingUtilities.invokeAndWait(()->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible())w.dispose();Map<String,Object> d=new LinkedHashMap<>();d.put("accounts",new ArrayList<>());Map<String,Object> pending=new LinkedHashMap<>();pending.put("attempt_id","pending-two");pending.put("label","Unfinished test connection");d.put("pending_attempts",Arrays.asList(pending));ui.chooseAccount(d);for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()&&"ChatGPT accounts and workspaces".equals(((JDialog)w).getTitle())){javax.swing.Timer answers=new javax.swing.Timer(50,e->{for(Window modal:Window.getWindows())if(modal instanceof JDialog&&modal.isVisible()&&("Unfinished sign-in".equals(((JDialog)modal).getTitle())||"Remove connection".equals(((JDialog)modal).getTitle()))){JButton ok=(JButton)named((Container)modal,"OK");if(ok!=null){boolean last="Remove connection".equals(((JDialog)modal).getTitle());ok.doClick();if(last)((javax.swing.Timer)e.getSource()).stop();}}});answers.start();((JButton)named((Container)w,"Remove an unfinished sign-in")).doClick();break;}});for(int i=0;i<100&&!Files.exists(capture);i++)Thread.sleep(50);String pendingPayload=new String(Files.readAllBytes(capture),java.nio.charset.StandardCharsets.UTF_8);check(pendingPayload.contains("\"attempt_id\": \"pending-two\"")&&!pendingPayload.contains("\"account\""),"Wrong pending attempt removed");Thread.sleep(200);Files.deleteIfExists(capture);
   SwingUtilities.invokeAndWait(()->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible())w.dispose();Map<String,Object> empty=new LinkedHashMap<>();empty.put("accounts",new ArrayList<>());empty.put("pending_attempts",new ArrayList<>());empty.put("removed",true);ui.chooseAccount(empty);for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()){check(!named((Container)w,"Remove selected connection").isEnabled(),"Remove enabled for empty list");((JButton)named((Container)w,"Close")).doClick();}});Thread.sleep(200);check(!Files.exists(capture),"Last removal started a new sign-in");
   String actual=System.getProperty("os.name");System.setProperty("os.name","Windows 11");check(WorkflowPanel.pythonExecutable("R").endsWith("/python/python.exe"),"Windows Python path");check(WorkflowPanel.javaExecutable("R").endsWith("java.exe"),"Windows Java path");check(WorkflowPanel.nullDevice().getPath().equals("NUL"),"Windows stderr device");System.setProperty("os.name",actual);
   System.out.println("PASS actual Swing account picker: same-email registrations separate, new dynamic account intent, selected reauthorization/switch/removal, cancelled removal, targeted unfinished removal, empty picker without auth, Windows resource paths; no real auth or credentials touched");System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(1);}
 }
}
