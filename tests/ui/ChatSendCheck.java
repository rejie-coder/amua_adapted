package v21;
import gui.frmMain;
import javax.swing.*;
import java.awt.*;
public class ChatSendCheck {
 static WorkflowPanel ui;static boolean sawReview,sawBudget;static int requests;
 static void check(boolean b,String why){if(!b)throw new AssertionError(why);}
 public static void main(String[] args)throws Exception{final boolean live=args.length>0&&"live".equals(args[0]);try{
 SwingUtilities.invokeAndWait(()->{frmMain app=new frmMain("0.3.6");app.frmMain.setSize(1280,800);WorkflowPanel.install(app);ui=(WorkflowPanel)((JSplitPane)app.frmMain.getContentPane()).getLeftComponent();app.frmMain.setVisible(true);
 javax.swing.Timer approvals=new javax.swing.Timer(50,e->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isShowing()){String title=((JDialog)w).getTitle();if("Review outgoing sources".equals(title)||"Review AI request".equals(title)){if("Review outgoing sources".equals(title))sawReview=true;else sawBudget=true;for(Component c:((JDialog)w).getContentPane().getComponents())if(c instanceof JOptionPane)((JOptionPane)c).setValue(JOptionPane.OK_OPTION);}}});approvals.start();
 ui.message.setText(live?"Reply exactly AMUA_CHAT_OK. This is a desktop connectivity test.":"chat-send-test");
 JButton send=(JButton)AccountPickerCheck.named(ui,"Send");check(send!=null&&send.isShowing()&&send.isEnabled(),"Send button unavailable");send.doClick();});
 boolean completed=false;for(int i=0;i<(live?1800:200);i++){final boolean[] b={false};SwingUtilities.invokeAndWait(()->{String transcript=ui.conversation.getText();b[0]=transcript.contains(live?"ChatGPT: AMUA_CHAT_OK":"ChatGPT: chat-send-response");if(ui.status.getText().equals("Needs attention")||ui.status.getText().startsWith("Operation failed"))throw new AssertionError("Send failed: "+ui.status.getText());});if(b[0]){completed=true;break;}Thread.sleep(100);}
 check(completed,"Send did not return a response");check(sawReview&&sawBudget,"Send did not show source/budget approval");SwingUtilities.invokeAndWait(()->{check(ui.project==null&&ui.paths.isEmpty(),"Unexpected source/model changes");check(!ui.activity.isVisible()&&!ui.activityTimer.isRunning(),"Busy indicator remained active after response");});
 System.out.println(live?"PASS real ChatGPT plain chat through visible Send button, outgoing/budget review and packaged helper; AMUA_CHAT_OK response; no files or model sent, one approved call":"PASS actual Swing Send button→outgoing review→budget approval→delayed helper reply; response visible and activity stopped; synthetic provider");System.exit(0);
 }catch(Throwable e){e.printStackTrace();System.exit(1);}}
}
