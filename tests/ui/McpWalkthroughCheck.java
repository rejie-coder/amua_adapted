package v21;
import javax.swing.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.nio.file.*;
import java.util.*;
import java.io.*;
import javax.imageio.ImageIO;
public class McpWalkthroughCheck {
 static void check(boolean v,String message){if(!v)throw new AssertionError(message);}
 public static void main(String[] args)throws Exception{
  try{
   final Path out=Paths.get(args[0]);Files.createDirectories(out);
   String resources="/tmp/Amua's folder/Amua.app/Contents/Resources";Map<String,Object> setups=new LinkedHashMap<>();
   for(String client:McpAccess.CLIENTS){String payload=McpAccess.configuration(client,resources);check(payload.contains("amua_324"),"Missing server alias");check(!payload.contains("3.1.3"),"Old release reference");setups.put(client,payload);}
   Files.write(out.resolve("setup-fixtures.json"),WorkflowPanel.json(setups).getBytes(java.nio.charset.StandardCharsets.UTF_8));
   check(McpAccess.isEnabled(),"New access should be available for requested connections");McpAccess.setEnabled(false);check(!McpAccess.isEnabled(),"Access off not persisted");McpAccess.setEnabled(true);check(McpAccess.isEnabled(),"Access on not persisted");
   SwingUtilities.invokeAndWait(()->{try{
    java.lang.reflect.Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);sun.misc.Unsafe unsafe=(sun.misc.Unsafe)f.get(null);
    gui.frmMain app=(gui.frmMain)unsafe.allocateInstance(gui.frmMain.class);ConnectionHandoffCheck.FrameHost frame=(ConnectionHandoffCheck.FrameHost)unsafe.allocateInstance(ConnectionHandoffCheck.FrameHost.class);frame.content=new JPanel();frame.menu=new JMenuBar();frame.menu.add(new JMenu("File"));frame.menu.add(new JMenu("Help"));app.frmMain=frame;app.language=new lang.Language();
    McpAccess.install(app);check("MCP Access".equals(frame.menu.getMenu(1).getText())&&"Help".equals(frame.menu.getMenu(2).getText()),"MCP Access is not adjacent to Help");
    JPanel panel=McpAccess.createPanel(null);panel.setSize(900,650);layout(panel);
    JTabbedPane tabs=find(panel,JTabbedPane.class);check(tabs.getTabCount()==4,"Walkthrough steps missing");JComboBox clients=find(panel,JComboBox.class);check(clients.getItemCount()==6,"Client choices missing");
    for(String client:McpAccess.CLIENTS){clients.setSelectedItem(client);JTextArea config=null;for(Component c:all(panel))if(c instanceof JTextArea&&"MCP setup configuration".equals(c.getName()))config=(JTextArea)c;check(config!=null&&config.getText().equals(McpAccess.configuration(client,System.getProperty("amua.resources"))),"Client selection did not update setup");}
    tabs.setSelectedIndex(1);clients.setSelectedItem("Codex");layout(panel);BufferedImage image=new BufferedImage(900,650,BufferedImage.TYPE_INT_ARGB);Graphics2D g=image.createGraphics();panel.printAll(g);g.dispose();ImageIO.write(image,"png",out.resolve("mcp-walkthrough.png").toFile());
   }catch(Exception e){throw new RuntimeException(e);}});
   System.out.println("PASS actual MCP walkthrough components: adjacent Help access action, four steps, six clients, persistent toggle, generated relocated/quoted setup and rendered panel");System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(1);}
 }
 static void layout(Container c){c.doLayout();for(Component child:c.getComponents())if(child instanceof Container)layout((Container)child);}
 static java.util.List<Component> all(Container c){java.util.List<Component> list=new ArrayList<>();for(Component child:c.getComponents()){list.add(child);if(child instanceof Container)list.addAll(all((Container)child));}return list;}
 static <T> T find(Container c,Class<T> kind){for(Component child:all(c))if(kind.isInstance(child))return kind.cast(child);return null;}
}
