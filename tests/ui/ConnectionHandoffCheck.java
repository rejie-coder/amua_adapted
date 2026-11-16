package v21;
import gui.frmMain;
import lang.Language;
import javax.swing.*;
import java.awt.*;
import java.lang.reflect.Field;
import java.util.Map;

/** Real sidebar/workers/helper subprocesses; inert frame host permits headless CI. */
public class ConnectionHandoffCheck {
    public static class FrameHost extends JFrame {
        Container content;JMenuBar menu;String title;
        public Container getContentPane(){return content;}
        public void setContentPane(Container c){content=c;}
        public JMenuBar getJMenuBar(){return menu;}
        public void setTitle(String s){title=s;}
        public String getTitle(){return title;}
    }
    static sun.misc.Unsafe unsafe;
    static WorkflowPanel ui;
    static void check(boolean value,String why){if(!value)throw new AssertionError(why);}
    static WorkflowPanel create() throws Exception {
        frmMain app=(frmMain)unsafe.allocateInstance(frmMain.class);
        FrameHost frame=(FrameHost)unsafe.allocateInstance(FrameHost.class);
        frame.content=new JPanel();frame.menu=new JMenuBar();app.frmMain=frame;app.language=new Language();
        WorkflowPanel panel=new WorkflowPanel(app);panel.preferences.putBoolean("chatgpt_plan_notice_shown",true);
        return panel;
    }
    static void idle() throws Exception {
        for(int i=0;i<200;i++){
            final boolean[] idle={false};SwingUtilities.invokeAndWait(()->idle[0]=!ui.activityTimer.isRunning());
            if(idle[0])return;Thread.sleep(25);
        }
        throw new AssertionError("Helper did not finish");
    }
    public static void main(String[] args) throws Exception {
        try {
            Field field=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");field.setAccessible(true);unsafe=(sun.misc.Unsafe)field.get(null);
            SwingUtilities.invokeAndWait(()->{try{ui=create();}catch(Exception e){throw new RuntimeException(e);}});
            SwingUtilities.invokeAndWait(()->{});idle();
            SwingUtilities.invokeAndWait(()->{
                check(ui.status.getText().startsWith("Using ChatGPT plan"),"Startup did not load saved connection");
                check(ui.conversation.getText().indexOf("Connected to ChatGPT")<0,"Quiet startup polluted chat");
                check(ui.app.frmMain.getTitle().equals("Amua (ReyJay) V 3.3.2 - Engine 0.3.6"),"Wrong title");
                JPanel top=(JPanel)ui.getComponent(0);top.setSize(340,600);top.doLayout();
                check(top.getComponent(0).getX()==ui.status.getX(),"Title/subtext left edges differ");
                for(Component child:top.getComponents())if(child instanceof JComponent)check(((JComponent)child).getAlignmentX()==Component.LEFT_ALIGNMENT,"Sidebar child has mixed alignment");
                ui.connectAccount("add",null);
            });
            Thread.sleep(250);
            SwingUtilities.invokeAndWait(()->{
                long epoch=ui.epoch.get();ui.provider("status");
                check(ui.epoch.get()==epoch&&ui.activityTimer.isRunning(),"Status cancelled an active sign-in");
                check("connect".equals(ui.lastRequest.get("action")),"Status replaced sign-in request");
            });
            Thread.sleep(200);
            SwingUtilities.invokeAndWait(()->check(ui.status.getText().contains("Verifying"),"Auth progress was not streamed to UI"));
            idle();SwingUtilities.invokeAndWait(()->{
                check(ui.status.getText().startsWith("Using ChatGPT plan"),"Completed sign-in did not update status");
                check(!ui.activity.isVisible(),"Completed sign-in left busy bar active");
                ui.connectAccount("add",null);ui.stop();
            });
            Thread.sleep(1500);
            SwingUtilities.invokeAndWait(()->{
                check(ui.status.getText().startsWith("Stopped"),"Late helper replaced Stop state");
                check(ui.process==null,"Cancelled helper retained process ownership");
                Map<String,Object> error=ui.req("unused");error.put("message","Code rejected");error.put("category","http_400_invalid_grant");error.put("request_id","req_synthetic_123");
                check(WorkflowPanel.friendlyError(error).contains("Reason: http_400_invalid_grant"),"Reason hidden");
                check(WorkflowPanel.friendlyError(error).contains("Request ID: req_synthetic_123"),"Request ID hidden");
            });
            System.out.println("PASS headless Swing sidebar with inert frame host and real helper subprocess: saved connection startup, left alignment/title, streamed sign-in stages, Status preserves sign-in, completion status, Stop/late process rejection, visible diagnostic reason/request ID");
            System.exit(0);
        }catch(Throwable error){error.printStackTrace();System.exit(1);}
    }
}
