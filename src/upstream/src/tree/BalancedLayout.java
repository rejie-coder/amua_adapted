package tree;
import java.util.*;
/** Deterministic ordered subtree layout. Coordinates are computed before application. */
public final class BalancedLayout {
    public static int[][] positions(int[][] children,int[] widths,int[] heights,int columnGap,int rowGap) {
        int n=children.length;
        if(n==0)return new int[0][2];
        int[] depth=new int[n],state=new int[n];List<Integer> order=new ArrayList<>();
        ArrayDeque<Integer> queue=new ArrayDeque<>();queue.add(0);state[0]=1;int maxDepth=0;
        while(!queue.isEmpty()){int i=queue.remove();order.add(i);for(int c:children[i]){if(c<0||c>=n||state[c]!=0)throw new IllegalArgumentException("Invalid tree topology");state[c]=1;depth[c]=depth[i]+1;maxDepth=Math.max(maxDepth,depth[c]);queue.add(c);}}
        if(order.size()!=n)throw new IllegalArgumentException("Unreachable nodes");
        int[] band=new int[n],column=new int[maxDepth+1],x=new int[maxDepth+1];
        for(int i=0;i<n;i++)column[depth[i]]=Math.max(column[depth[i]],widths[i]);
        x[0]=50;for(int d=1;d<x.length;d++)x[d]=x[d-1]+column[d]+columnGap;
        for(int p=order.size()-1;p>=0;p--){int i=order.get(p),sum=0;for(int c:children[i])sum+=band[c]+rowGap;if(children[i].length>0)sum-=rowGap;band[i]=Math.max(heights[i],sum);}
        int[][] out=new int[n][2];int[] top=new int[n];top[0]=50;
        for(int i:order){int[] cs=children[i];int sum=0;for(int c:cs)sum+=band[c]+rowGap;if(cs.length>0)sum-=rowGap;int next=top[i]+(band[i]-sum)/2;for(int c:cs){top[c]=next;next+=band[c]+rowGap;}out[i][0]=x[depth[i]];}
        for(int p=order.size()-1;p>=0;p--){int i=order.get(p);int[] cs=children[i];out[i][1]=cs.length==0?top[i]+band[i]/2:(out[cs[0]][1]+out[cs[cs.length-1]][1])/2;}
        return out;
    }
}
