import base.AmuaModel;
import tree.TreeNode;
import gui.frmMain;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import javax.imageio.ImageIO;
import javax.swing.*;
import javax.xml.bind.JAXBContext;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.*;

/** Runs the real OCD action and painters against identical synthetic model copies. */
public class CompactDisplayRegression {
    static Object field(Object o,String name)throws Exception{
        Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);
    }
    static void check(boolean b,String why){if(!b)throw new AssertionError(why);}
    static String content(AmuaModel m)throws Exception{
        StringWriter w=new StringWriter();JAXBContext.newInstance(AmuaModel.class).createMarshaller().marshal(m,w);
        Document d=DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(new ByteArrayInputStream(w.toString().getBytes(StandardCharsets.UTF_8)));
        for(String tag:new String[]{"xPos","yPos","parentX","parentY"}){
            NodeList list=d.getElementsByTagName(tag);
            while(list.getLength()>0){Node n=list.item(0);n.getParentNode().removeChild(n);}
        }
        javax.xml.transform.Transformer t=javax.xml.transform.TransformerFactory.newInstance().newTransformer();
        StringWriter out=new StringWriter();t.transform(new javax.xml.transform.dom.DOMSource(d),new javax.xml.transform.stream.StreamResult(out));return out.toString();
    }
    static String positions(AmuaModel m){
        StringBuilder out=new StringBuilder();
        for(int i=0;i<m.tree.nodes.size();i++){
            TreeNode n=m.tree.nodes.get(i);
            out.append(i+","+n.xPos+","+n.yPos+","+n.parentX+","+n.parentY+"\n");
        }
        return out.toString();
    }
    public static void main(String[] args)throws Exception{
        SwingUtilities.invokeAndWait(()->{try{
            frmMain app=new frmMain("0.3.6");
            app.frmMain.setBounds(30,40,1680,955);
            app.openModel(new File(args[0]));
            AmuaModel m=(AmuaModel)field(app,"curModel");
            String before=content(m);
            m.panelTree.ocd("OCD regression",true);
            check(before.equals(content(m)),"OCD changed model content beyond coordinates");
            String right=positions(m);
            Files.write(Paths.get(args[1]+"-right.csv"),right.getBytes(StandardCharsets.UTF_8));
            m.panelTree.ocd("Repeated OCD",true);
            check(right.equals(positions(m)),"Repeated OCD drifted");
            int maxX=0,maxY=0;for(TreeNode n:m.tree.nodes){maxX=Math.max(maxX,n.xPos);maxY=Math.max(maxY,n.yPos);}
            if(args[2].equals("fixed")){
                check(maxX==780&&maxY==740,"Compact 80% bounds differ from original: "+maxX+","+maxY);
                for(TreeNode n:m.tree.nodes)if(n.type==2)check(n.xPos==maxX,"Right alignment ignored");
            }
            m.panelTree.setSize(m.panelTree.getPreferredSize());
            BufferedImage image=new BufferedImage(2*m.panelTree.getWidth(),2*m.panelTree.getHeight(),BufferedImage.TYPE_INT_RGB);
            Graphics2D g=image.createGraphics();g.setColor(Color.WHITE);g.fillRect(0,0,image.getWidth(),image.getHeight());g.scale(2,2);m.panelTree.printAll(g);g.dispose();
            ImageIO.write(image,"png",new File(args[1]+"-tree.png"));
            if(args[2].equals("fixed")){
                for(TreeNode n:m.tree.nodes){
                    int rgb=image.getRGB(2*(n.xPos+n.width/2),2*(n.yPos+n.height/2))&0xffffff;
                    int expected=n.type==0?0xff0000:n.type==1?0x00ff00:0x0000ff;
                    check(rgb==expected,"Muted/incorrect node fill for "+n.name+": "+Integer.toHexString(rgb));
                }
            }
            m.panelTree.ocd("Left alignment",false);
            Files.write(Paths.get(args[1]+"-left.csv"),positions(m).getBytes(StandardCharsets.UTF_8));
            check(before.equals(content(m)),"Left OCD changed clinical model content");
            System.out.println("PASS real OCD: "+m.tree.nodes.size()+" nodes; right bounds "+maxX+"x"+maxY+"; stable repeat; scientific fields unchanged; left/right coordinate records; canvas rendered"+(args[2].equals("fixed")?"; original compact bounds and saturated fills verified":""));
            app.frmMain.dispose();System.exit(0);
        }catch(Throwable e){e.printStackTrace();System.exit(1);}});
    }
}
