package base;
import java.util.WeakHashMap;
/** Preserve subpixel coordinate history across legacy integer display scales. EDT only. */
public final class ZoomCoordinates {
    private static final WeakHashMap<ModelNode,Position> positions=new WeakHashMap<>();
    private static final class Position {double x,y;int shownX,shownY;Position(ModelNode n,int scale){capture(n,scale);}void capture(ModelNode n,int scale){x=n.xPos*100.0/scale;y=n.yPos*100.0/scale;shownX=n.xPos;shownY=n.yPos;}}
    public static void rescale(ModelNode node,int oldScale,int newScale){
        if(oldScale<=0||newScale<=0)throw new IllegalArgumentException("Scale must be positive");
        Position p=positions.get(node);
        if(p==null){p=new Position(node,oldScale);positions.put(node,p);}
        else if(node.xPos!=p.shownX||node.yPos!=p.shownY)p.capture(node,oldScale);
        node.xPos=(int)Math.round(p.x*newScale/100.0);node.yPos=(int)Math.round(p.y*newScale/100.0);
        p.shownX=node.xPos;p.shownY=node.yPos;
    }
}
