import gui.frmMain;
import base.AmuaModel;
import tree.TreeNode;
import java.util.*;
import javax.swing.*;
public class EngineLayoutCheck {
 static Object field(Object o,String name)throws Exception{java.lang.reflect.Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
 static TreeNode add(AmuaModel m,TreeNode parent,int type)throws Exception{java.lang.reflect.Field f=m.panelTree.getClass().getDeclaredField("curNode");f.setAccessible(true);f.set(m.panelTree,parent);m.addNode(type);return (TreeNode)f.get(m.panelTree);}
 static void check(boolean b,String why){if(!b)throw new AssertionError(why);}
 public static void main(String[] args)throws Exception{SwingUtilities.invokeAndWait(()->{try{
  frmMain app=new frmMain("0.3.6");((JMenuItem)field(app,"mntmDecisionTree")).doClick(0);AmuaModel m=(AmuaModel)field(app,"curModel");TreeNode root=m.tree.nodes.get(0);
  TreeNode a=add(m,root,1);a.name="A very long treatment label with Unicode — 日本語 and source details";a.textName.setText(a.name);
  TreeNode a1=add(m,a,2);a1.prob="0.25";a1.payoff[0]="100";TreeNode a2=add(m,a,2);a2.prob="C";a2.payoff[0]="20";
  main.Console console=(main.Console)field(app,"console");check(m.checkModel(console,true),"fixture validation");m.runModel(console,true);m.getStrategies();double ev=m.getStrategyEV(0,0);check(ev==40.0,"expected arithmetic");
  List<List<Integer>> order=new ArrayList<>();for(TreeNode n:m.tree.nodes)order.add(new ArrayList<>(n.childIndices));
  m.panelTree.ocd("Measured layout",false);for(int i=0;i<order.size();i++)check(order.get(i).equals(m.tree.nodes.get(i).childIndices),"order changed");m.runModel(console,true);m.getStrategies();check(m.getStrategyEV(0,0)==ev,"layout changed calculation");
  int[][] xy=new int[m.tree.nodes.size()][2];for(int i=0;i<xy.length;i++){xy[i][0]=m.tree.nodes.get(i).xPos;xy[i][1]=m.tree.nodes.get(i).yPos;}boolean dirty=m.unsavedChanges;
  for(int round=0;round<20;round++)for(int scale:new int[]{50,75,100,125,150,200,100})m.rescale(scale);
  for(int i=0;i<xy.length;i++)check(xy[i][0]==m.tree.nodes.get(i).xPos&&xy[i][1]==m.tree.nodes.get(i).yPos,"actual tree drift");check(m.unsavedChanges==dirty,"zoom changed dirty");
  m.panelTree.automaticLayout=true;int before=m.tree.nodes.size();TreeNode extra=add(m,a,2);extra.prob="0";extra.payoff[0]="999";check(m.tree.nodes.size()==before+1,"auto insertion");m.undoAction();check(m.tree.nodes.size()==before,"one undo insertion");m.redoAction();check(m.tree.nodes.size()==before+1,"redo insertion");
  for(String lang:new String[]{"en","fr","es","pt","km","zh"}){ResourceBundle bundle=ResourceBundle.getBundle("v21.WorkflowText",new Locale(lang));for(String key:ResourceBundle.getBundle("v21.WorkflowText",Locale.ENGLISH).keySet())check(!bundle.getString(key).isEmpty(),"missing fallback");}
  System.out.println("PASS actual engine layout arithmetic/order, tree zoom 20 cycles/dirty state, automatic insertion single undo/redo, six-locale control fallback");System.exit(0);
 }catch(Throwable e){e.printStackTrace();System.exit(1);}});}
}
