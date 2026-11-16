import tree.BalancedLayout;
import java.util.*;
public class LayoutCheck {
  static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
  static int[][] run(int[][] c){int[] w=new int[c.length],h=new int[c.length];Arrays.fill(w,300);Arrays.fill(h,110);return BalancedLayout.positions(c,w,h,35,20);}
  public static void main(String[] args){
    int[][] children={{1,2,3},{4,5},{},{6},{},{},{}};
    int[][] p=run(children);check(Arrays.deepEquals(p,run(children)),"idempotence");check(p[0][1]==(p[1][1]+p[3][1])/2,"first/last centering");check(p[4][1]<p[5][1]&&p[5][1]<p[2][1]&&p[2][1]<p[6][1],"sibling order");
    for(int i=0;i<p.length;i++)for(int j=i+1;j<p.length;j++)if(p[i][0]==p[j][0])check(Math.abs(p[i][1]-p[j][1])>=110,"same-depth overlap");
    try{run(new int[][]{{1},{0}});throw new AssertionError("cycle accepted");}catch(IllegalArgumentException expected){}
    try{run(new int[][]{{},{}});throw new AssertionError("orphan accepted");}catch(IllegalArgumentException expected){}
    for(int count:new int[]{100,1000,5000,10000}){
      int[][] cs=new int[count][];for(int i=0;i<count;i++){int first=i*2+1;cs[i]=first>=count?new int[0]:first+1>=count?new int[]{first}:new int[]{first,first+1};}
      long[] times=new long[25];for(int t=0;t<25;t++){long start=System.nanoTime();run(cs);times[t]=System.nanoTime()-start;}Arrays.sort(times);System.out.printf(Locale.ROOT,"nodes=%d layout_p95_ms=%.3f%n",count,times[23]/1e6);
    }
    System.out.println("PASS ordered layout, centering, no same-depth intersections, topology rejection, deterministic repeated runs");
  }
}
