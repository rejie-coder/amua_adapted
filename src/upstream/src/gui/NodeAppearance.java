package gui;

import java.awt.*;

/** Original high-contrast Amua colours, with isolated antialiased rendering. */
public final class NodeAppearance {
    private NodeAppearance() {}
    private static final Color[] FILLS={Color.RED,Color.GREEN,Color.BLUE,Color.ORANGE};
    public static void paint(Graphics graphics,Shape shape,int x,int y,int width,int height,
                             boolean selected,boolean collapsed,int palette){
        Graphics2D g=(Graphics2D)graphics.create();
        try{
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);
            g.setColor(collapsed?Color.LIGHT_GRAY:FILLS[palette]);
            g.fill(shape);
            g.setColor(selected?Color.RED:Color.BLACK);
            g.setStroke(new BasicStroke(2f));
            g.draw(shape);
        }finally{g.dispose();}
        // Match the original black connectors (red for selection).
        graphics.setColor(selected?Color.RED:Color.BLACK);
        ((Graphics2D)graphics).setStroke(new BasicStroke(2f));
    }
}
