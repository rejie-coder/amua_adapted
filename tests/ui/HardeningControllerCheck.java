package v21;
import javax.swing.*;
import java.nio.file.*;
import java.util.*;
import base.AmuaModel;

/** Real native panels, guarded edits, Undo and safe source-inventory copy. */
public class HardeningControllerCheck {
 static void layout(java.awt.Container container){container.doLayout();for(java.awt.Component child:container.getComponents())if(child instanceof java.awt.Container)layout((java.awt.Container)child);}
 public static void main(String[] args)throws Exception{
  SwingUtilities.invokeAndWait(()->{try{
   gui.frmMain app=ModelChatControllerCheck.host();String xml=new String(Files.readAllBytes(Paths.get(args[0])),java.nio.charset.StandardCharsets.UTF_8);
   ModelChat.apply(app,xml,null,null,false);AmuaModel original=(AmuaModel)ModelChatControllerCheck.get(app,"curModel");
   ModelChatControllerCheck.require(original.tree.nodes.get(1).hasVarUpdates,"Original native update flag absent");
   String hash=(String)WorkspaceSnapshot.capture(original).get("sha256");
   String corrected=new String(Files.readAllBytes(Paths.get(args[1])),java.nio.charset.StandardCharsets.UTF_8);
   ModelChat.apply(app,corrected,original,hash,true);
   ModelChatControllerCheck.require(original.tree.nodes.get(1).hasVarUpdates&&"x=5".equals(original.tree.nodes.get(1).varUpdates),"Undoable edit dropped variable update");
   ModelChatControllerCheck.require(original.checkModel(app.workflowConsole(),true),"Preserved model fails original checker");
   original.undoAction();ModelChatControllerCheck.require("x=5".equals(original.tree.nodes.get(1).varUpdates),"Undo dropped update");original.redoAction();
   Map before=WorkspaceSnapshot.capture(original);AmuaModel copy=ModelChat.withoutSourceInventory(original);
   Map state=ModelChat.state(copy);ModelChatControllerCheck.require(state!=null&&!state.containsKey("evidence"),"Copy retained embedded inventory");
   ModelChatControllerCheck.require("x=5".equals(copy.tree.nodes.get(1).varUpdates),"Copy changed executable behavior");
   ModelChatControllerCheck.require(before.get("sha256").equals(WorkspaceSnapshot.capture(original).get("sha256")),"Copy mutated original");
   WorkflowPanel ui=new WorkflowPanel(app);ui.stop();ModelChatControllerCheck.require(!ui.includeEmbeddedEvidence.isSelected(),"Saved inventory enabled by default");
   Map<String,Object> suggestion=new LinkedHashMap<>(),suggestedAction=new LinkedHashMap<>(),request=new LinkedHashMap<>();suggestion.put("text","Synthetic remote run suggestion");suggestedAction.put("intent","run");suggestion.put("proposal",suggestedAction);request.put("text","Review without running");request.put("workspace",WorkspaceSnapshot.capture(original));ui.receiveChat(suggestion,request);
   ModelChatControllerCheck.require(ui.process==null&&!ui.activityTimer.isRunning()&&ui.conversation.getText().contains("not executed"),"Remote suggestion authorized an analysis");
   ui.setSize(340,600);layout(ui);java.awt.Point location=SwingUtilities.convertPoint(ui.message,0,0,ui);
   ModelChatControllerCheck.require(location.y>=0&&location.y+ui.message.getHeight()<=600,"Question field is outside the short sidebar");
   java.awt.image.BufferedImage image=new java.awt.image.BufferedImage(340,600,java.awt.image.BufferedImage.TYPE_INT_ARGB);java.awt.Graphics2D graphics=image.createGraphics();ui.printAll(graphics);graphics.dispose();javax.imageio.ImageIO.write(image,"png",Paths.get(args[2]).toFile());
   System.out.println("PASS actual Swing native update retention, full original validation, Undo/Redo, detached source-inventory copy and privacy default");System.exit(0);
  }catch(Throwable error){error.printStackTrace();System.exit(1);}});
 }
}
