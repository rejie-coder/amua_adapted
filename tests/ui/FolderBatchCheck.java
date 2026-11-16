package v21;
import gui.frmMain;
import javax.swing.*;
import java.awt.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

/** Isolated actual Swing/helper test. Never attaches to a running app or sends AI requests. */
public final class FolderBatchCheck {
 static frmMain app;static WorkflowPanel ui;static int checks;static javax.swing.Timer cancel;
 interface Probe{boolean ready()throws Exception;}
 static void check(boolean ok,String why){if(!ok)throw new AssertionError(why);checks++;}
 static <T>T edt(java.util.concurrent.Callable<T> task)throws Exception{AtomicReference<T> value=new AtomicReference<>();AtomicReference<Throwable> error=new AtomicReference<>();SwingUtilities.invokeAndWait(()->{try{value.set(task.call());}catch(Throwable e){error.set(e);}});if(error.get()!=null)throw new RuntimeException(error.get());return value.get();}
 static void waitFor(Probe p,String why)throws Exception{for(int n=0;n<300;n++){if(edt(()->p.ready()))return;Thread.sleep(100);}throw new AssertionError("Timed out: "+why+"; "+edt(()->ui.status.getText()+" project_present="+(ui.project!=null)+" pending="+(ui.selectionPlan==null?-1:ui.pendingSources())+" selection="+(ui.selectionPlan==null?"none":WorkflowPanel.json(ui.selectionPlan))+" "+ui.conversation.getText()));}
 static java.util.List<Map> entries(){return (java.util.List<Map>)(java.util.List)ui.selectionPlan.get("entries");}
 static int countStatus(String status){int n=0;for(Map e:entries())if(status.equals(e.get("status")))n++;return n;}
 static java.util.List<Map> files(){return (java.util.List<Map>)(java.util.List)((Map)ui.project.get("provenance")).get("files");}
 static void clear(){ui.stop();ui.project=null;ui.selectionPlan=null;ui.history.clear();}
 static JButton button(Component root,String title){if(root instanceof JButton&&title.equals(((JButton)root).getText()))return (JButton)root;if(root instanceof Container)for(Component c:((Container)root).getComponents()){JButton found=button(c,title);if(found!=null)return found;}return null;}
 static boolean cancelDialog(Component component){if(component instanceof JOptionPane){((JOptionPane)component).setValue(JOptionPane.CANCEL_OPTION);return true;}if(component instanceof Container)for(Component c:((Container)component).getComponents())if(cancelDialog(c))return true;return false;}
 public static void main(String[]args)throws Exception{
  try{
   Path folder=Files.createTempDirectory("amua-folder-ui-").toRealPath();for(int i=0;i<25;i++)Files.write(folder.resolve(String.format("source-%02d.txt",i)),("Unique source "+i+"\nCost item "+i+"\n").getBytes(StandardCharsets.UTF_8));
   Files.createDirectory(folder.resolve("nested"));Files.write(folder.resolve("nested/child.txt"),"Nested source\n".getBytes(StandardCharsets.UTF_8));Files.write(folder.resolve(".hidden.txt"),"Hidden\n".getBytes(StandardCharsets.UTF_8));Files.write(folder.resolve("legacy.doc"),"Unsupported legacy Word binary fixture".getBytes(StandardCharsets.UTF_8));
   edt(()->{app=new frmMain("0.3.6");app.frmMain.setExtendedState(JFrame.NORMAL);app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setVisible(true);ui.paths.add(folder.toString());ui.includeSubfolders.setSelected(false);ui.workflow("intake");return null;});
   waitFor(()->ui.selectionPlan!=null&&ui.pendingSources()==0&&ui.process==null&&ui.project!=null,"flat folder batches");
   edt(()->{check(entries().size()==26,"flat folder must preserve 25 TXT plus unsupported file");for(Map metadata:entries())for(String key:new String[]{"mtime_ns","device","inode"})check(metadata.get(key) instanceof String,"file metadata precision not preserved: "+key);check(countStatus("inventoried")==25,"25 text inputs not inventoried");check(countStatus("unsupported")==1,"unsupported file silently omitted");check(ui.conversation.getText().contains("unsupported"),"unsupported-source warning absent from UI");check(files().size()==26,"all physical source manifests must survive batching");check(((java.util.List)ui.selectionPlan.get("exclusions")).size()==2,"hidden/nested exclusions missing");check("draft_incomplete".equals(ui.project.get("state")),"physical intake became executable");check("workflow".equals(ui.lastHelper)&&ui.history.isEmpty(),"provider was invoked during local folder read");clear();ui.includeSubfolders.setSelected(true);ui.workflow("intake");return null;});
   waitFor(()->ui.selectionPlan!=null&&ui.pendingSources()==0&&ui.process==null&&ui.project!=null,"recursive folder batches");
   edt(()->{check(entries().size()==27,"recursive scope must include nested source");check(countStatus("inventoried")==26&&countStatus("unsupported")==1,"recursive statuses incorrect");boolean nested=false;for(Map e:entries())if(String.valueOf(e.get("display_path")).contains("nested/child.txt"))nested=true;check(nested,"nested identity not retained");check(((java.util.List)ui.selectionPlan.get("exclusions")).size()==1,"hidden source exclusion missing");
    ui.message.setText("Summarize all selected source facts without executing anything.");cancel=new javax.swing.Timer(80,e->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()&&"Review outgoing sources".equals(((JDialog)w).getTitle()))cancelDialog(w);});cancel.start();ui.send();cancel.stop();check("workflow".equals(ui.lastHelper)&&ui.history.isEmpty(),"cancelled outgoing review reached provider");return null;});
   edt(()->{clear();ui.message.setText("Read this entire folder locally and prepare a review.");cancel=new javax.swing.Timer(80,e->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()&&"Review outgoing sources".equals(((JDialog)w).getTitle()))cancelDialog(w);});cancel.start();ui.send();return null;});
   waitFor(()->{if(ui.project==null||ui.pendingSources()!=0||ui.process!=null)return false;for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()&&"Review outgoing sources".equals(((JDialog)w).getTitle()))return false;return true;},"Send auto-inspection folder chain and review cancellation");
   edt(()->{cancel.stop();check(entries().size()==27&&files().size()==27,"Send folder chain lost sources");check("workflow".equals(ui.lastHelper)&&ui.history.isEmpty(),"cancelled automatic folder review reached provider");return null;});
   edt(()->{for(Map e:entries())e.put("status","pending");ui.project=null;Map plan=ui.selectionPlan;ui.readFolderBatch(0,null);ui.stop();check(ui.selectionPlan==plan&&ui.project==null,"Stop replaced project/selection immediately");return null;});
   Thread.sleep(700);edt(()->{check(ui.project==null&&ui.pendingSources()==27,"late reply applied after Stop");JButton resume=button(ui,"Continue folder reading");check(resume!=null&&resume.isEnabled(),"visible resume button missing");resume.doClick();return null;});
   waitFor(()->ui.project!=null&&ui.pendingSources()==0&&ui.process==null,"resume explicit pending batch");
   edt(()->{check(entries().size()==27&&files().size()==27,"resume dropped or duplicated physical sources");Set<String> ids=new HashSet<>();for(Map f:files())ids.add(String.valueOf(f.get("id")));check(ids.size()==27,"source IDs merged during resume");check("workflow".equals(ui.lastHelper)&&ui.history.isEmpty(),"resume contacted provider");System.out.println("PASS "+checks+" folder UI checks: 25 TXT, unsupported ledger, nested scope, review cancel, Stop/visible-button resume; zero provider calls");app.frmMain.dispose();return null;});System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(1);}
 }
}
