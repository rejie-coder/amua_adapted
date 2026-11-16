package v21;
import javax.swing.*;
import java.nio.file.*;
import java.util.*;
import base.AmuaModel;
import javax.script.*;

/** Actual native sidebar methods and models, no top-level desktop or real service. */
public class ImageChatControllerCheck {
 static Map json(Path path)throws Exception{ScriptEngine e=new ScriptEngineManager().getEngineByName("nashorn");e.put("payload",new String(Files.readAllBytes(path),java.nio.charset.StandardCharsets.UTF_8));return (Map)e.eval("Java.asJSONCompatible(JSON.parse(payload))");}
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 static void near(double actual,double expected){check(Math.abs(actual-expected)<1e-8,"Expected "+expected+", got "+actual);}
 public static void main(String[] args)throws Exception{
  SwingUtilities.invokeAndWait(()->{try{
   Path folder=Paths.get(args[0]);gui.frmMain app=ModelChatControllerCheck.host();WorkflowPanel ui=new WorkflowPanel(app);ui.stop();
   Map<String,Object> preview=json(folder.resolve("preview.json")),proposal=json(folder.resolve("proposal-response.json")),confirmed=json(folder.resolve("confirmed-response.json"));
   Map<String,Object> request=ui.chatRequest("Create a decision tree from this image");check(!request.containsKey("workspace"),"Unexpected initial model evidence");
   ui.acceptPreliminaryOutline(preview);AmuaModel outline=ui.model();check(outline.tree.nodes.size()==2,"Expected preliminary outline");check(outline.name.contains("PRELIMINARY"),"Outline looks like final output");
   Map<String,Object> followup=ui.chatRequest("Create a decision tree from this image");check(!followup.containsKey("workspace"),"Unchanged source outline contaminated the next Send");
   ui.recordProposalFailure("invalid_question_target",request);check(ui.pendingChat==null&&ui.conversation.getText().contains("FINAL TREE NOT APPLIED"),"Failure looks like success");
   ui.lastRequest=new LinkedHashMap<>(request);ui.lastRequest.put("action","chat-request");ui.lastHelper="provider";
   Map retry=ui.retryRequest();check("chat-preview".equals(retry.get("action")),"Retry bypasses a fresh review");check(String.valueOf(retry.get("history")).contains("invalid_question_target"),"Retry forgot the validation reason");check(!ui.activityTimer.isRunning(),"Failure triggered an automatic retry");
   ui.receiveChat(proposal,followup);check(ui.pendingChat!=null&&ui.pendingTarget==outline,"Final proposal not bound to unchanged outline");check(ui.applyProposal.isEnabled(),"Ready proposal has no enabled apply control");
   ui.setSize(340,600);HardeningControllerCheck.layout(ui);java.awt.Point button=SwingUtilities.convertPoint(ui.applyProposal,0,0,ui);check(button.y>=0&&button.y+ui.applyProposal.getHeight()<150,"Apply control is hidden below scrolling sources");
   java.awt.image.BufferedImage screenshot=new java.awt.image.BufferedImage(340,600,java.awt.image.BufferedImage.TYPE_INT_ARGB);java.awt.Graphics2D graphics=screenshot.createGraphics();ui.printAll(graphics);graphics.dispose();javax.imageio.ImageIO.write(screenshot,"png",folder.resolve("sidebar-proposal-ready.png").toFile());
   ui.applyPendingChat(true);AmuaModel model=ui.model();check(model==outline,"Expected reviewed in-place outline replacement");
   check(model.tree.nodes.size()==7&&model.dimInfo.dimNames.length==2,"Image did not become a two-dimension seven-node tree");
   check(!model.checkModel(app.workflowConsole(),true),"Unreviewed image inputs calculated");
   ui.chatTarget=model;ui.chatTargetHash=(String)WorkspaceSnapshot.capture(model).get("sha256");ui.receiveChat(confirmed,followup);
   check(model.checkModel(app.workflowConsole(),true),"Explicitly reviewed model failed full native checker");
   check(model.parameters.size()==12,"Source parameters missing or guard not cleared");
   model.undoAction();check(!model.checkModel(app.workflowConsole(),true),"Undo did not restore review guard");model.redoAction();check(model.checkModel(app.workflowConsole(),true),"Redo failed");
   Path saved=Files.createTempDirectory(Paths.get(System.getProperty("amua.support")),"image-model-").resolve("Swing-created image model.amua");base.AtomicModelSave.save(model,saved,false);
   Map result=ChatEngine.run(ChatEngine.load(saved));List rows=(List)result.get("results");check(rows.size()==4,"Missing outcome results");
   for(Object value:rows){Map row=(Map)value;double expected="Drug A".equals(row.get("strategy"))?("Cost ($)".equals(row.get("outcome"))?850:1.55):("Cost ($)".equals(row.get("outcome"))?1520:2.2);near(((Number)row.get("value")).doubleValue(),expected);}
   // ChatEngine returns the native comparison table rounded to four decimals.
   // The separate image pipeline verifies the unrounded incremental calculation.
   boolean found=false;for(Object item:(List)result.get("comparison_table")){Object[] row=(Object[])item;if("Drug B".equals(row[1])){near(((Number)row[4]).doubleValue(),1030.7692);found=true;}}
   check(found,"Original CEA table lacks Drug B ICER");
   // A genuine manual change to the outline must be included, never discarded.
   ui.acceptPreliminaryOutline(preview);ui.model().tree.nodes.get(1).name="User edited outline";
   check(ui.chatRequest("Edit my draft").containsKey("workspace"),"Manual edits to an outline were discarded");
   System.out.println("PASS image-chat sidebar: preliminary/final separation, safe retry, no outline contamination, reviewed replacement, input guard, Undo/Redo, 7 nodes/2 dimensions, original engine 850/1.55 and 1520/2.20, comparison-table ICER 1030.7692");System.exit(0);
  }catch(Throwable error){error.printStackTrace();System.exit(1);}});
 }
}
