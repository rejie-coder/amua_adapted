package v21;
import gui.frmMain;
import javax.swing.*;
import java.awt.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
/** Real synthetic Excel -> actual sidebar Send/preview/approval -> online helper. */
public class WorkbookOnlineCheck {
    static WorkflowPanel ui; static frmMain app;
    static boolean outgoing,budget; static volatile String failure;
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static JOptionPane pane(Container parent){for(Component c:parent.getComponents()){if(c instanceof JOptionPane)return (JOptionPane)c;if(c instanceof Container){JOptionPane result=pane((Container)c);if(result!=null)return result;}}return null;}
    public static void main(String[] args)throws Exception{
        try {
            SwingUtilities.invokeAndWait(()->{
                app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);
                ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setTitle("Synthetic XLSX online acceptance — isolated test");app.frmMain.setVisible(true);
                javax.swing.Timer dialogs=new javax.swing.Timer(50,event->{
                    for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isShowing()){
                        JDialog d=(JDialog)w;JOptionPane option=pane(d.getContentPane());
                        if("Review outgoing sources".equals(d.getTitle())){
                            if(ui.project==null){failure="Outgoing preview had no inspected workbook";option.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                            java.util.List files=(java.util.List)((Map)ui.project.get("provenance")).get("files");Map file=(Map)files.get(0);int cells=0;
                            for(Object s:(java.util.List)file.get("sheets"))cells+=((java.util.List)((Map)s).get("cells")).size();
                            if(cells!=4){failure="Expected four synthetic workbook cells";option.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                            outgoing=true;option.setValue(JOptionPane.OK_OPTION);d.dispose();
                        }else if("Approve request budget".equals(d.getTitle())){
                            String info=String.valueOf(option.getMessage());Matcher calls=Pattern.compile("requires ([0-9.]+) remote calls").matcher(info);
                            if(!outgoing||!calls.find()||Double.parseDouble(calls.group(1))!=1){failure="Budget preview was not exactly one call";option.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                            budget=true;option.setValue(JOptionPane.OK_OPTION);d.dispose();
                        }
                    }
                });dialogs.start();
                ui.paths.add(args[0]);ui.message.setText("From the inspected synthetic workbook, report the text in A1 and the cached calculated value in D1. These values must come from the workbook evidence. Do not invent missing inputs.");ui.send();
            });
            boolean done=false;
            for(int i=0;i<1200;i++){
                final boolean[] terminal={false};SwingUtilities.invokeAndWait(()->terminal[0]=failure!=null||ui.conversation.getText().contains("ChatGPT:")||ui.status.getText().equals("Needs attention")||ui.status.getText().startsWith("Operation failed"));
                if(terminal[0]){done=true;break;}Thread.sleep(50);
            }
            final String[] transcript={""};SwingUtilities.invokeAndWait(()->transcript[0]=ui.conversation.getText());Files.write(Paths.get(args[1]),transcript[0].getBytes(StandardCharsets.UTF_8));
            check(done,"Timed out waiting for actual workbook online response");check(failure==null,failure);check(outgoing&&budget,"Actual UI previews were not approved");
            check(transcript[0].contains("ChatGPT:"),"No successful ChatGPT UI response: "+transcript[0]);
            check(transcript[0].contains("AMUA_XLSX_7D62")&&transcript[0].contains("35"),"Reply did not verify file-derived marker and calculation");
            check(transcript[0].contains("1/1"),"Source-chunk acknowledgement missing");
            System.out.println("PASS actual Send -> local4cell XLSX inspection -> outgoing review -> exact1call approval -> online file-derived marker+35 -> chunk1/1 acknowledgement; existing user app untouched");System.exit(0);
        }catch(Throwable e){e.printStackTrace();System.exit(1);}
    }
}
