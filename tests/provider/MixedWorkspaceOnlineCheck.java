package v21;
import gui.frmMain;
import base.AmuaModel;
import javax.swing.*;
import java.awt.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.lang.reflect.Field;
import java.util.*;
import java.util.regex.*;
/** Synthetic manual workspace -> reviewed AI suggestion, never model edits. */
public class MixedWorkspaceOnlineCheck {
    static WorkflowPanel ui;static frmMain app;static AmuaModel model;
    static boolean outgoing,budget;static int approvedCalls;static boolean requestSaved;static volatile String failure;static String beforeHash;
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static Field field(Object target,String name)throws Exception{for(Class type=target.getClass();type!=null;type=type.getSuperclass()){try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f;}catch(NoSuchFieldException ignored){}}throw new NoSuchFieldException(name);}
    static Object get(Object target,String name)throws Exception{return field(target,name).get(target);}
    static void set(Object target,String name,Object value)throws Exception{field(target,name).set(target,value);}
    static JOptionPane pane(Container parent){for(Component c:parent.getComponents()){if(c instanceof JOptionPane)return (JOptionPane)c;if(c instanceof Container){JOptionPane p=pane((Container)c);if(p!=null)return p;}}return null;}
    public static void main(String[] args)throws Exception{
        final long start=System.nanoTime();
        try{
            SwingUtilities.invokeAndWait(()->{try{
                app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();
                ((JMenuItem)get(app,"mntmDecisionTree")).doClick(0);model=ui.model();model.name="SYNTH_WORKSPACE_MODEL_Q7";
                set(model.panelTree,"curNode",model.tree.nodes.get(0));model.addNode(1);model.tree.nodes.get(1).name="SYNTH_STRATEGY_Q7";
                set(model.panelTree,"curNode",model.tree.nodes.get(1));model.addNode(2);model.tree.nodes.get(2).name="SYNTH_KNOWN_BRANCH_Q7";model.tree.nodes.get(2).prob="0.4";model.tree.nodes.get(2).payoff[0]="77";
                set(model.panelTree,"curNode",model.tree.nodes.get(1));model.addNode(2);model.tree.nodes.get(3).name="SYNTH_MISSING_BRANCH_Q7";model.tree.nodes.get(3).prob="";model.tree.nodes.get(3).payoff[0]="19";
                for(tree.TreeNode node:model.tree.nodes){Object name=get(node,"textName");if(name instanceof javax.swing.text.JTextComponent)((javax.swing.text.JTextComponent)name).setText(node.name==null?"":node.name);if(node.parentType!=0){Object prob=get(node,"textProb");if(prob instanceof javax.swing.text.JTextComponent)((javax.swing.text.JTextComponent)prob).setText(node.prob);}if(node.type==2){Object payoff=get(node,"textPayoff");if(payoff instanceof javax.swing.text.JTextComponent)((javax.swing.text.JTextComponent)payoff).setText("("+model.dimInfo.dimSymbols[0]+") "+node.payoff[0]);}}
                beforeHash=String.valueOf(WorkspaceSnapshot.capture(model).get("sha256"));
                app.frmMain.setTitle("Synthetic mixed folder + manual workspace review — isolated test");app.frmMain.setVisible(true);
                javax.swing.Timer approve=new javax.swing.Timer(50,event->{if(budget&&!requestSaved&&ui.lastRequest!=null&&"request".equals(ui.lastRequest.get("action"))){try{Files.write(Paths.get(args[4]+".synthetic-request.json"),WorkflowPanel.json(ui.lastRequest).getBytes(StandardCharsets.UTF_8));requestSaved=true;}catch(Exception error){failure="Cannot preserve synthetic request fixture";ui.stop();}}for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isShowing()){
                    JDialog d=(JDialog)w;JOptionPane p=pane(d.getContentPane());
                    if("Review outgoing sources".equals(d.getTitle())){
                        Map request=ui.lastRequest;
                        outgoing=true;p.setValue(JOptionPane.OK_OPTION);d.dispose();
                    }else if("Approve request budget".equals(d.getTitle())){
                        Matcher calls=Pattern.compile("requires ([0-9.]+) remote calls").matcher(String.valueOf(p.getMessage()));
                        if(!outgoing||!calls.find()||(Double.parseDouble(calls.group(1))<1||Double.parseDouble(calls.group(1))>2)){failure="Mixed-folder request exceeded two-call test approval";p.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                        Map project=(Map)ui.lastRequest.get("project");
                        if(project==null||!(project.get("workspace_model") instanceof Map)){failure="Workspace model missing from actual outgoing UI request";p.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                        String local=WorkflowPanel.json(project);for(int i=1;i<=3;i++)if(!local.contains(args[i])){failure="Local extraction did not include an expected synthetic document value";p.setValue(JOptionPane.CANCEL_OPTION);d.dispose();return;}
                        approvedCalls=(int)Double.parseDouble(calls.group(1));budget=true;p.setValue(JOptionPane.OK_OPTION);d.dispose();
                    }
                }});approve.start();
                ui.paths.add(args[0]);ui.includeSubfolders.setSelected(true);ui.message.setText("Read all selected documents, including the scanned page, and report their identifying text and prices. Identify the current manual model by name and point out its missing branch-probability gap. Do not execute, change the model, or invent missing facts.");ui.send();
            }catch(Exception e){throw new RuntimeException(e);}});
            boolean done=false;for(int i=0;i<2400;i++){
                final boolean[] terminal={false};SwingUtilities.invokeAndWait(()->terminal[0]=failure!=null||ui.conversation.getText().contains("ChatGPT:")||ui.status.getText().equals("Needs attention")||ui.status.getText().startsWith("Operation failed"));
                if(terminal[0]){done=true;break;}Thread.sleep(50);
            }
            final String[] conversation={""},afterHash={""};SwingUtilities.invokeAndWait(()->{conversation[0]=ui.conversation.getText();afterHash[0]=String.valueOf(WorkspaceSnapshot.capture(model).get("sha256"));});
            check(done,"Timed out waiting for workspace review");check(failure==null,failure);check(outgoing&&budget,"Workspace review/approval missing");
            check(conversation[0].contains("ChatGPT:"),"No successful workspace response; inspect sanitized error category");
            check(conversation[0].contains("SYNTH_WORKSPACE_MODEL_Q7")&&conversation[0].contains("SYNTH_MISSING_BRANCH_Q7")&&conversation[0].toLowerCase().contains("probab"),"Reply did not identify actual workspace name and missing branch probability");
            for(int i=1;i<=3;i++)check(conversation[0].contains(args[i]),"Online response omitted an expected synthetic document value");
            check(Pattern.compile("\\b25\\b").matcher(conversation[0]).find(),"Online response omitted DOCX25price");
            check(beforeHash.equals(afterHash[0]),"Online review changed workspace XML");
            Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("actual_ui_send",true);result.put("outgoing_review",outgoing);result.put("approved_calls",approvedCalls);result.put("workspace_name_and_probability_gap_verified",true);result.put("docx_html_scanned_pdf_values_verified",true);result.put("folder_plan_used",ui.selectionPlan!=null);result.put("source_files_read",((java.util.List)((Map)ui.project.get("provenance")).get("files")).size());result.put("workspace_xml_unchanged",true);result.put("private_original_files_uploaded",0);result.put("real_user_models_touched",false);result.put("duration_seconds",(System.nanoTime()-start)/1e9);
            Files.write(Paths.get(args[4]),WorkflowPanel.json(result).getBytes(StandardCharsets.UTF_8));System.out.println("PASS actualUI mixedfolder DOCX+HTML+scannedPDF/OCR -> reviewed/approved1-2calls -> documentvalues/modelname/missingprobability verified -> workspace XML unchanged");System.exit(0);
        }catch(Throwable e){try{Map<String,Object> r=new LinkedHashMap<>();r.put("success",false);r.put("error_type",e.getClass().getSimpleName());r.put("error",String.valueOf(e.getMessage()));r.put("raw_transcript_saved",false);Files.write(Paths.get(args[4]),WorkflowPanel.json(r).getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){}e.printStackTrace();System.exit(1);}
    }
}
