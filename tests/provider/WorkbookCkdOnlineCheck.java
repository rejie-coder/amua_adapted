package v21;
import gui.frmMain;
import javax.swing.*;
import java.awt.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
/** Real synthetic Excel -> actual sidebar Send/preview/approval -> online helper. */
public class WorkbookCkdOnlineCheck {
    static WorkflowPanel ui; static frmMain app;
    static boolean outgoing,budget; static long started=System.nanoTime(); static volatile String failure;
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static JOptionPane pane(Container parent){for(Component c:parent.getComponents()){if(c instanceof JOptionPane)return (JOptionPane)c;if(c instanceof Container){JOptionPane result=pane((Container)c);if(result!=null)return result;}}return null;}
    public static void main(String[] args)throws Exception{
        try {
            SwingUtilities.invokeAndWait(()->{
                app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);
                ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setTitle("CKD workbook online acceptance — isolated test");app.frmMain.setVisible(true);
                javax.swing.Timer dialogs=new javax.swing.Timer(50,event->{
                    for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isShowing()){
                        JDialog d=(JDialog)w;JOptionPane option=pane(d.getContentPane());
                        if("Review outgoing sources".equals(d.getTitle())){
                            if(ui.project==null){failure="Outgoing preview had no inspected workbook";option.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                            java.util.List files=(java.util.List)((Map)ui.project.get("provenance")).get("files");Map file=(Map)files.get(0);int cells=0;
                            for(Object s:(java.util.List)file.get("sheets"))cells+=((java.util.List)((Map)s).get("cells")).size();
                            if(cells!=2269){failure="Expected2269physical workbook cells";option.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                            outgoing=true;option.setValue(JOptionPane.OK_OPTION);d.dispose();
                        }else if("Approve request budget".equals(d.getTitle())){
                            String info=String.valueOf(option.getMessage());Matcher calls=Pattern.compile("requires ([0-9.]+) remote calls").matcher(info);
                            if(!outgoing||!calls.find()||Double.parseDouble(calls.group(1))!=29){failure="Budget preview was not exactly29calls";option.setValue(JOptionPane.CANCEL_OPTION);d.dispose();continue;}
                            budget=true;option.setValue(JOptionPane.OK_OPTION);d.dispose();
                        }
                    }
                });dialogs.start();
                ui.paths.add(args[0]);ui.message.setText("Can you see this Excel workbook? Identify the sheets and source errors; do not execute or claim scientific validity. Use the inspected source records, preserve unresolved references and do not invent missing inputs.");ui.send();
            });
            boolean done=false;
            for(int i=0;i<24000;i++){
                final boolean[] terminal={false};SwingUtilities.invokeAndWait(()->terminal[0]=failure!=null||ui.conversation.getText().contains("ChatGPT:")||ui.status.getText().equals("Needs attention")||ui.status.getText().startsWith("Operation failed"));
                if(terminal[0]){done=true;break;}Thread.sleep(50);
            }
            final String[] transcript={""};SwingUtilities.invokeAndWait(()->transcript[0]=ui.conversation.getText());
            check(done,"Timed out waiting for actual workbook online response");check(failure==null,failure);check(outgoing&&budget,"Actual UI previews were not approved");
            check(transcript[0].contains("ChatGPT:"),"No successful ChatGPT UI response; inspect sanitized helper error category");
            check(transcript[0].contains("29/29"),"Complete29chunk acknowledgement missing");
            final int[] sheetsFound={0};final int[] localErrors={0};final int[] localSheets={0};
            SwingUtilities.invokeAndWait(()->{java.util.List files=(java.util.List)((Map)ui.project.get("provenance")).get("files");Map file=(Map)files.get(0);for(Object sheet:(java.util.List)file.get("sheets")){localSheets[0]++;if(transcript[0].contains(String.valueOf(((Map)sheet).get("name"))))sheetsFound[0]++;for(Object cell:(java.util.List)((Map)sheet).get("cells"))if("source-error".equals(((Map)cell).get("value_kind")))localErrors[0]++;}});
            Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("source_chunks_acknowledged",29);result.put("physical_cells",2269);result.put("local_sheet_count",localSheets[0]);result.put("local_cached_errors",localErrors[0]);result.put("sheet_names_found_in_response_count",sheetsFound[0]);result.put("duration_seconds",(System.nanoTime()-started)/1e9);result.put("outgoing_review",outgoing);result.put("exact29call_approval",budget);result.put("raw_transcript_saved",false);result.put("scientific_model_promoted",false);
            Files.write(Paths.get(args[1]),WorkflowPanel.json(result).getBytes(StandardCharsets.UTF_8));
            System.out.println("PASS actual CKD Send ->2269cells/6sheets/24errors inspected -> reviewed/approved29calls -> all29chunks acknowledged; raw transcript not saved; no model promoted");System.exit(0);
        }catch(Throwable e){try{Map<String,Object> r=new LinkedHashMap<>();r.put("success",false);r.put("error_type",e.getClass().getSimpleName());r.put("error",String.valueOf(e.getMessage()));r.put("outgoing_review",outgoing);r.put("exact29call_approval",budget);r.put("raw_transcript_saved",false);Files.write(Paths.get(args[1]),WorkflowPanel.json(r).getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){}e.printStackTrace();System.exit(1);}
    }
}
