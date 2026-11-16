package v21;
import gui.frmMain;
import javax.swing.*;
import java.awt.*;
import java.util.*;

/** User regression: select CKD workbook then Send without clicking Inspect sources. */
public class WorkflowSendCheck {
    static WorkflowPanel ui;
    static frmMain app;
    static boolean outgoingShown;
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void waitFor(java.util.concurrent.Callable<Boolean> condition)throws Exception{
        for(int i=0;i<200;i++){
            final boolean[] done={false};
            SwingUtilities.invokeAndWait(()->{try{done[0]=condition.call();}catch(Exception e){throw new RuntimeException(e);}});
            if(done[0])return;
            Thread.sleep(50);
        }
        throw new AssertionError("Timed out waiting for source preparation");
    }
    public static void main(String[] args)throws Exception{
        try{
            SwingUtilities.invokeAndWait(()->{
                app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);
                WorkflowPanel.install(app);
                ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();
                app.frmMain.setVisible(true);
                ui.paths.add(args[0]);ui.message.setText("Explain this CKD workbook");
                ui.send();
                check("workflow".equals(ui.lastHelper),"Send did not start local inspection");
            });
            waitFor(()->{
                for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isShowing()&&"Review outgoing sources".equals(((JDialog)w).getTitle())){
                    check(ui.project!=null,"Review opened without a derived project");
                    java.util.List files=(java.util.List)((Map)ui.project.get("provenance")).get("files");
                    Map source=(Map)files.get(0);int cells=0,errors=0;
                    for(Object sheet:(java.util.List)source.get("sheets"))for(Object cell:(java.util.List)((Map)sheet).get("cells")){cells++;if("source-error".equals(((Map)cell).get("value_kind")))errors++;}
                    check(cells==2269&&errors==24,"Send lost source records or errors");
                    check("workflow".equals(ui.lastHelper),"Remote helper ran before outgoing review");
                    outgoingShown=true;
                    for(Component c:((JDialog)w).getContentPane().getComponents())if(c instanceof JOptionPane)((JOptionPane)c).setValue(JOptionPane.CANCEL_OPTION);
                    w.dispose();return true;
                }
                return false;
            });
            SwingUtilities.invokeAndWait(()->{
                check(outgoingShown,"Outgoing review not shown");
                check("workflow".equals(ui.lastHelper),"Cancelling review still invoked provider");
                check(!ui.conversation.getText().contains("derive_workbook_before_sending"),"Internal error still shown");
                ui.project=null;ui.send();ui.stop();
            });
            Thread.sleep(700);
            SwingUtilities.invokeAndWait(()->{
                check(ui.project==null,"Stopped preparation applied a late result");
                check(!WorkflowPanel.friendlyError("derive_workbook_before_sending").contains("derive_workbook_before_sending"),"Friendly fallback leaked error code");
                ui.paths.clear();ui.paths.add(args[0]+".missing");ui.send();
            });
            waitFor(()->ui.status.getText().equals("Needs attention"));
            SwingUtilities.invokeAndWait(()->{
                check(ui.project==null,"Failed intake created a project");
                check("workflow".equals(ui.lastHelper),"Failed intake called provider");
                check(!ui.conversation.getText().contains("{\"ok\":false"),"Raw error response shown");
            });
            System.out.println("PASS select-workbook then Send auto-inspects all2269cells/24errors before review; cancel/Stop/failure never send; friendly error fallback");
            System.exit(0);
        }catch(Throwable error){error.printStackTrace();System.exit(1);}
    }
}
