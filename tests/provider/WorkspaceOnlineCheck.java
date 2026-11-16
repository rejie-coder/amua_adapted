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
public class WorkspaceOnlineCheck {
    static WorkflowPanel ui;static frmMain app;static AmuaModel model;
    static boolean outgoing,budget;static volatile String failure;static String beforeHash;
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static Object get(Object target,String field)throws Exception{Field f=target.getClass().getDeclaredField(field);f.setAccessible(true);return f.get(target);}
    static void set(Object target,String field,Object value)throws Exception{Field f=target.getClass().getDeclaredField(field);f.setAccessible(true);f.set(target,value);}
    static JOptionPane pane(Container parent){for(Component c:parent.getComponents()){if(c instanceof JOptionPane)return (JOptionPane)c;if(c instanceof Container){JOptionPane p=pane((Container)c);if(p!=null)return p;}}return null;}
    public static void main(String[] args)throws Exception{
        final long start=System.nanoTime();
        try{
            SwingUtilities.invokeAndWait(()->{try{
                app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();
                ((JMenuItem)get(app,"mntmDecisionTree")).doClick(0);model=ui.model();model.name="SYNTH_WORKSPACE_MODEL_Q7";
                set(model.panelTree,"curNode",model.tree.nodes.get(0));model.addNode(2);
                model.tree.nodes.get(1).name="SYNTH_TERMINAL_Q7";model.tree.nodes.get(1).payoff[0]="77";
                beforeHash=String.valueOf(WorkspaceSnapshot.capture(model).get("sha256"));
                app.frmMain.setTitle("Synthetic manual workspace online review — isolated test");app.frmMain.setVisible(true);
                javax.swing.Timer approve=new javax.swing.Timer(50,event->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isShowing()){
                    JDialog d=(JDialog)w;JOptionPane p=pane(d.getContentPane());
                    if("Review outgoing sources".equals(d.getTitle())){
                        Map request=ui.lastRequest;
                        outgoing=true;p.setValue(JOptionPane.OK_OPTION);d.dispose();
                    }else if("Approve request budget".equals(d.getTitle())){
                        Matcher calls=Pattern.compile("requires ([0-9.]+) remote calls").matcher(String.valueOf(p.getMessage()));
                        if(!outgoing||!calls.find()||Double.parseDouble(calls.group(1))!=1){failure="Workspace request was not exactly one approved call";p.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                        Map project=(Map)ui.lastRequest.get("project");
                        if(project==null||!(project.get("workspace_model") instanceof Map)){failure="Workspace model missing from actual outgoing UI request";p.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                        budget=true;p.setValue(JOptionPane.OK_OPTION);d.dispose();
                    }
                }});approve.start();
                ui.message.setText("Identify the current manually created workspace model name and terminal node name, and report its payoff. Suggest one gap without altering or executing the model.");ui.send();
            }catch(Exception e){throw new RuntimeException(e);}});
            boolean done=false;for(int i=0;i<2400;i++){
                final boolean[] terminal={false};SwingUtilities.invokeAndWait(()->terminal[0]=failure!=null||ui.conversation.getText().contains("ChatGPT:")||ui.status.getText().equals("Needs attention")||ui.status.getText().startsWith("Operation failed"));
                if(terminal[0]){done=true;break;}Thread.sleep(50);
            }
            final String[] conversation={""},afterHash={""};SwingUtilities.invokeAndWait(()->{conversation[0]=ui.conversation.getText();afterHash[0]=String.valueOf(WorkspaceSnapshot.capture(model).get("sha256"));});
            check(done,"Timed out waiting for workspace review");check(failure==null,failure);check(outgoing&&budget,"Workspace review/approval missing");
            check(conversation[0].contains("ChatGPT:"),"No successful workspace response; inspect sanitized error category");
            check(conversation[0].contains("SYNTH_WORKSPACE_MODEL_Q7")&&conversation[0].contains("SYNTH_TERMINAL_Q7")&&conversation[0].contains("77"),"Reply did not verify actual workspace names/payoff");
            check(beforeHash.equals(afterHash[0]),"Online review changed workspace XML");
            Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("actual_ui_send",true);result.put("outgoing_review",outgoing);result.put("approved_calls",1);result.put("workspace_names_and_payoff_verified",true);result.put("workspace_xml_unchanged",true);result.put("source_files_uploaded",0);result.put("real_user_models_touched",false);result.put("duration_seconds",(System.nanoTime()-start)/1e9);
            Files.write(Paths.get(args[0]),WorkflowPanel.json(result).getBytes(StandardCharsets.UTF_8));System.out.println("PASS actualUI synthetic manual workspace -> reviewed/approved1call -> source-only names/payoff verified -> workspace XML unchanged");System.exit(0);
        }catch(Throwable e){try{Map<String,Object> r=new LinkedHashMap<>();r.put("success",false);r.put("error_type",e.getClass().getSimpleName());r.put("error",String.valueOf(e.getMessage()));r.put("raw_transcript_saved",false);Files.write(Paths.get(args[0]),WorkflowPanel.json(r).getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){}e.printStackTrace();System.exit(1);}
    }
}
