package gui;

import java.awt.*;

/** Presentation only: model types, bounds, hit testing and calculations stay in the engine. */
public final class NodeAppearance {
    private NodeAppearance() {}

    public static void paint(Graphics graphics, Shape shape, int x, int y, int width, int height,
                             boolean selected, boolean collapsed, int palette) {
        Color[] fills = {new Color(248, 213, 209), new Color(211, 237, 223),
                         new Color(215, 228, 250), new Color(250, 230, 194)};
        Color[] outlines = {new Color(181, 79, 71), new Color(53, 125, 88),
                            new Color(70, 105, 169), new Color(159, 108, 32)};
        Graphics2D g = (Graphics2D) graphics.create();
        try {
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            Color fill = collapsed ? new Color(225, 229, 234) : fills[palette];
            Color top = new Color(Math.min(255, fill.getRed()+12), Math.min(255, fill.getGreen()+12), Math.min(255, fill.getBlue()+12));
            g.setPaint(new GradientPaint(x, y, top, x, y+Math.max(1, height), fill));
            g.fill(shape);
            g.setColor(selected ? new Color(190, 49, 56) : collapsed ? new Color(119, 130, 143) : outlines[palette]);
            g.setStroke(new BasicStroke(selected ? 2.4f : 1.6f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
            g.draw(shape);
        } finally { g.dispose(); }
        // Existing connector and label placement follows this call.
        graphics.setColor(selected ? new Color(190, 49, 56) : new Color(65, 76, 92));
        ((Graphics2D) graphics).setStroke(new BasicStroke(1.6f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
    }
}
