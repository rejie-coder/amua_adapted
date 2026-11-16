import base.ModelNode;
import base.ZoomCoordinates;
public class ZoomCheck {
 public static void main(String[] args){for(int original:new int[]{50,75,100,125,150,200})for(int coordinate:new int[]{1,33,117,619,1043}){ModelNode n=new ModelNode();n.xPos=coordinate;n.yPos=coordinate+13;int prev=original;for(int i=0;i<20;i++){for(int scale:new int[]{50,75,100,125,150,200,original}){ZoomCoordinates.rescale(n,prev,scale);prev=scale;}if(n.xPos!=coordinate||n.yPos!=coordinate+13)throw new AssertionError("drift");}n.xPos+=27;int changed=n.xPos;ZoomCoordinates.rescale(n,original,50);ZoomCoordinates.rescale(n,50,original);if(n.xPos!=changed)throw new AssertionError("edit lost");}System.out.println("PASS 30 coordinate/scale fixtures ×20 cycles; manual move preserved");}
}
