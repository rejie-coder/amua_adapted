package v21;
import gui.frmMain;
import javax.swing.*;
import java.util.*;
import java.awt.*;
public class WorkflowIntegrationCheck {
 static frmMain app;static WorkflowPanel ui;static volatile Map<String,Object> result;
 static void check(boolean b,String why){if(!b)throw new AssertionError(why);}
 static void awaitProject()throws Exception{for(int i=0;i<150;i++){SwingUtilities.invokeAndWait(()->result=ui.project);if(result!=null)return;Thread.sleep(100);}throw new AssertionError("No helper project result");}
 public static void main(String[] args)throws Exception{
  try{
   SwingUtilities.invokeAndWait(()->{app=new frmMain("0.3.6");app.frmMain.setExtendedState(JFrame.NORMAL);app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setVisible(true);for(String p:args)ui.paths.add(p);ui.workflow("intake");});
   awaitProject();Map graph=(Map)result.get("graph");check(((java.util.List)graph.get("nodes")).size()==50,"full D2P graph missing");check("draft_incomplete".equals(result.get("state")),"unsafe executable draft");
   SwingUtilities.invokeAndWait(()->{JMenuBar bar=app.frmMain.getJMenuBar();check(bar.getMenu(4).getText().equals("AI Workflow"),"menu order");try{java.lang.reflect.Field f=frmMain.class.getDeclaredField("tabbedPaneCanvas");f.setAccessible(true);JTabbedPane canvas=(JTabbedPane)f.get(app);check(canvas.getTabCount()==0,"draft became executable model");System.out.println("canvas_1280x800="+canvas.getWidth()+"x"+canvas.getHeight());check(canvas.getWidth()>=640&&canvas.getHeight()>=480,"canvas space below required minimum");}catch(ReflectiveOperationException e){throw new RuntimeException(e);}ui.review();});
   SwingUtilities.invokeAndWait(()->{for(Window w:Window.getWindows())if(w instanceof JDialog)w.dispose();ui.project=null;ui.invoke("workflow",ui.req("synthetic"));});awaitProject();check(((Map)result.get("parameters")).get("synthetic_fixture").equals(Boolean.TRUE),"synthetic fixture plumbing");
   SwingUtilities.invokeAndWait(()->{Map old=ui.project;ui.workflow("intake");ui.stop();check(ui.project==old,"Stop changed project");});Thread.sleep(1000);SwingUtilities.invokeAndWait(()->check(ui.project==result,"late cancelled reply applied"));
   System.out.println("PASS packaged helper/UI full D2P intake, isolated draft review, 1280x800 canvas, synthetic action, cancelled late-reply barrier");System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(1);}
 }
}
