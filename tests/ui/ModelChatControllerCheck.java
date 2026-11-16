package v21;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import base.AmuaModel;

/** Real native Swing panels/models, with an inert frame in the headless test host. */
public class ModelChatControllerCheck {
 static void set(Object o,String name,Object value)throws Exception{Field f=gui.frmMain.class.getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
 static Object get(Object o,String name)throws Exception{Field f=gui.frmMain.class.getDeclaredField(name);f.setAccessible(true);return f.get(o);}
 static void require(boolean condition,String why){if(!condition)throw new AssertionError(why);}
 static gui.frmMain host()throws Exception{
  Field u=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");u.setAccessible(true);sun.misc.Unsafe unsafe=(sun.misc.Unsafe)u.get(null);
  gui.frmMain app=(gui.frmMain)unsafe.allocateInstance(gui.frmMain.class);
  ConnectionHandoffCheck.FrameHost frame=(ConnectionHandoffCheck.FrameHost)unsafe.allocateInstance(ConnectionHandoffCheck.FrameHost.class);frame.content=new JPanel();frame.menu=new JMenuBar();app.frmMain=frame;app.language=new lang.Language();app.version="0.3.6";
  for(Field f:gui.frmMain.class.getDeclaredFields()){
   f.setAccessible(true);if(Modifier.isStatic(f.getModifiers())||f.get(app)!=null)continue;
   Class<?> type=f.getType();if(JComponent.class.isAssignableFrom(type))try{f.set(app,type.newInstance());}catch(Exception ignored){}
   if(type==DefaultTableModel.class)f.set(app,new DefaultTableModel(0,12));
  }
  app.tabbedPaneBottom.addTab("Console",new JPanel());app.tabbedPaneBottom.addTab("Notes",new JPanel());app.tabbedPaneBottom.addTab("Parameter sets",new JPanel());
  set(app,"modelList",new ArrayList<AmuaModel>());set(app,"modelTypes",new ArrayList<Integer>());set(app,"main",app);
  set(app,"console",new main.Console("0.3.6",app.language));set(app,"errorLog",new main.ErrorLog("0.3.6",app.language));app.clipboard=new main.Clipboard();return app;
 }
 public static void main(String[] args)throws Exception{
  SwingUtilities.invokeAndWait(()->{try{
   gui.frmMain app=host();String xml=new String(Files.readAllBytes(Paths.get(args[0])),java.nio.charset.StandardCharsets.UTF_8);
   ModelChat.apply(app,xml,null,null,false);AmuaModel model=(AmuaModel)get(app,"curModel");
   require(model!=null&&model.tree.nodes.size()==4,"Native tree absent");require(model.panelTree.getComponentCount()>0,"Canvas has no editable controls");
   Map before=WorkspaceSnapshot.capture(model);String hash=(String)before.get("sha256");
   String changed=xml.replace("<name>Synthetic</name>","<name>Edited</name>");
   ModelChat.apply(app,changed,model,hash,true);require(model.name.equals("Edited"),"Edit not applied");require(model.actionStackUndo.size()==1,"AI edit not undoable");
   model.undoAction();require(model.name.equals("Synthetic"),"Undo failed");model.redoAction();require(model.name.equals("Edited"),"Redo failed");
   try{ModelChat.apply(app,changed,model,hash,true);throw new AssertionError("Stale edit accepted");}catch(IllegalStateException expected){}
   require(model.checkModel(app.workflowConsole(),true),"Original full validation failed");
   Path path=Files.createTempDirectory(Paths.get(args[1]),"native-save-").resolve("model.amua");base.AtomicModelSave.save(model,path,false);AmuaModel reopened=base.AtomicModelSave.read(path);require(ModelChat.state(reopened)!=null,"Questions/provenance lost on save");require(reopened.tree.nodes.size()==4,"Tree lost on reopen");
   String unknown=new String(Files.readAllBytes(Paths.get(args[2])),java.nio.charset.StandardCharsets.UTF_8);ModelChat.apply(app,unknown,null,null,false);AmuaModel draft=(AmuaModel)get(app,"curModel");require(!draft.checkModel(app.workflowConsole(),true),"Incomplete tree passed original validation");
   require(((List)get(app,"modelList")).size()==2,"Existing model was replaced");require(!app.workflowTitle(new AmuaModel()).contains("null"),"Null title suffix remains");
   WorkflowPanel ui=new WorkflowPanel(app);ui.stop();
   // Return to the valid model and bind a local explicit answer to its exact revision.
   ((JTabbedPane)get(app,"tabbedPaneCanvas")).setSelectedIndex(0);java.lang.reflect.Method switcher=gui.frmMain.class.getDeclaredMethod("switchTabs");switcher.setAccessible(true);switcher.invoke(app);
   ui.chatTarget=model;ui.chatTargetHash=(String)WorkspaceSnapshot.capture(model).get("sha256");
   Map<String,Object> reply=new LinkedHashMap<>();reply.put("text","Explicit user answer");reply.put("local_answer",true);reply.put("candidate_xml",xml.replace("<name>Synthetic</name>","<name>Answer applied</name>"));Map<String,Object> proposal=new LinkedHashMap<>();proposal.put("intent","edit");reply.put("proposal",proposal);
   ui.receiveChat(reply,new LinkedHashMap<>());require(model.name.equals("Answer applied"),"Chat answer did not reach native model");model.undoAction();require(model.name.equals("Edited"),"Chat answer undo failed");
   String beforeTimeout=(String)WorkspaceSnapshot.capture(model).get("sha256");ui.activeAction="engine-analysis";ui.activityStarted=System.nanoTime()-111000000000L;ui.updateActivity();require(!ui.activityTimer.isRunning()&&ui.process==null,"Deadline did not stop operation");require(WorkspaceSnapshot.capture(model).get("sha256").equals(beforeTimeout),"Timeout changed model");require(ui.conversation.getText().contains("deadline"),"Deadline not explained in chat");
   model.panelTree.setSize(1200,600);java.awt.image.BufferedImage image=new java.awt.image.BufferedImage(1200,600,java.awt.image.BufferedImage.TYPE_INT_ARGB);java.awt.Graphics2D g=image.createGraphics();model.panelTree.printAll(g);g.dispose();javax.imageio.ImageIO.write(image,"png",Paths.get(args[1]).resolve("editable-tree.png").toFile());
   System.out.println("PASS native editable Swing tree creation, revision-bound in-place edit, original Undo/Redo, stale edit rejection, original full validation, atomic native save/reopen with AI state, incomplete CKD draft blocked, original tab preserved title fallback, chat-to-native answer/undo, bounded deadline preserving model and rendered canvas");System.exit(0);
  }catch(Throwable error){error.printStackTrace();System.exit(1);}});
 }
}
