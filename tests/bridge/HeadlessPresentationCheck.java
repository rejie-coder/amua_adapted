import base.AmuaModel;
import base.ModelNode;
import base.ModelPanel;
import tree.TreeNode;
import tree.PanelTree;
import markov.MarkovNode;
import markov.PanelMarkov;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.lang.reflect.Field;
import java.util.List;
import javax.imageio.ImageIO;
import javax.swing.*;
import javax.xml.bind.JAXBContext;

/** Runs real node painters with Swing text fields and no top-level desktop window. */
public class HeadlessPresentationCheck {
    static String xml(AmuaModel m) throws Exception {
        StringWriter out=new StringWriter();JAXBContext.newInstance(AmuaModel.class).createMarshaller().marshal(m,out);return out.toString();
    }
    static void fields(ModelNode n, ModelPanel panel) throws Exception {
        n.textName=new JTextField(n.name);n.lblCollapsed=new JLabel("+");
        for(Field f:n.getClass().getDeclaredFields()){
            f.setAccessible(true);
            if(f.getType()==JLabel.class)f.set(n,new JLabel());
            else if(JComboBox.class.isAssignableFrom(f.getType()))f.set(n,new JComboBox<String>(new String[]{"State"}));
            else if(JTextField.class.isAssignableFrom(f.getType())){
                JTextField text;
                if(f.getType()==JTextField.class)text=new JTextField();
                else text=(JTextField)f.getType().getConstructor(panel.getClass(),n.getClass(),int.class).newInstance(panel,n,0);
                f.set(n,text);
            }
        }
    }
    static void text(Graphics2D g,JTextField field){
        field.setBorder(null);field.setOpaque(false);field.setFont(new Font("SansSerif",Font.PLAIN,12));
        if(field.getWidth()>0){Graphics2D c=(Graphics2D)g.create(field.getX(),field.getY(),field.getWidth(),field.getHeight());field.paint(c);c.dispose();}
    }
    public static void main(String[] args) throws Exception {
        Field unsafeField=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");unsafeField.setAccessible(true);
        sun.misc.Unsafe unsafe=(sun.misc.Unsafe)unsafeField.get(null);
        for(String path:args){
            AmuaModel m=HeadlessEngineCheck.load(path);String before=xml(m);boolean dirty=m.unsavedChanges;
            ModelPanel panel=(ModelPanel)unsafe.allocateInstance(m.type==0?PanelTree.class:PanelMarkov.class);panel.myModel=m;
            List<? extends ModelNode> nodes=m.type==0?m.tree.nodes:m.markov.nodes;
            for(ModelNode n:nodes)fields(n,panel);
            for(double zoom:new double[]{.5,1,2}){
                BufferedImage image=new BufferedImage(1400,900,BufferedImage.TYPE_INT_ARGB);Graphics2D g=image.createGraphics();
                g.setColor(Color.WHITE);g.fillRect(0,0,image.getWidth(),image.getHeight());g.scale(zoom,zoom);
                g.setColor(Color.MAGENTA);Stroke stroke=g.getStroke();
                for(ModelNode n:nodes){
                    for(int state=0;state<3;state++){
                        boolean selected=n.selected,collapsed=n.collapsed;n.selected=state==1;n.collapsed=state==2;
                        if(n instanceof TreeNode)((TreeNode)n).paintComponent(g);else ((MarkovNode)n).paintComponent(g);
                        n.selected=selected;n.collapsed=collapsed;
                        if(!Color.MAGENTA.equals(g.getColor())||!stroke.equals(g.getStroke()))throw new AssertionError("Painter leaked graphics state");
                    }
                    if(n instanceof TreeNode)((TreeNode)n).paintComponent(g);else ((MarkovNode)n).paintComponent(g);
                    text(g,n.textName);
                }
                g.dispose();
                if(zoom==1)ImageIO.write(image,"png",new File("evidence/"+(m.type==0?"tree":"markov")+"-313.png"));
                if(!before.equals(xml(m))||m.unsavedChanges!=dirty)throw new AssertionError("Painting changed model XML or dirty flag");
            }
        }
        System.out.println("PASS real tree/Markov node painters at 50/100/200% drawing scale; selected/collapsed states, unchanged model XML/dirty flag, isolated graphics state");
    }
}
