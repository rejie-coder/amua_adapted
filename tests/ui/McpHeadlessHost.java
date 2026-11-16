package v21;
import java.lang.reflect.Field;
import javax.swing.*;
public class McpHeadlessHost {
 public static gui.frmMain create()throws Exception{
  Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);sun.misc.Unsafe unsafe=(sun.misc.Unsafe)f.get(null);
  gui.frmMain app=(gui.frmMain)unsafe.allocateInstance(gui.frmMain.class);ConnectionHandoffCheck.FrameHost frame=(ConnectionHandoffCheck.FrameHost)unsafe.allocateInstance(ConnectionHandoffCheck.FrameHost.class);frame.content=new JPanel();frame.menu=new JMenuBar();app.frmMain=frame;app.language=new lang.Language();
  Field models=gui.frmMain.class.getDeclaredField("modelList");models.setAccessible(true);models.set(app,new java.util.ArrayList<base.AmuaModel>());return app;
 }
}
