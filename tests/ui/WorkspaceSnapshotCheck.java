package v21;
import gui.frmMain;
import base.AmuaModel;
import javax.swing.*;
import java.io.File;
import java.util.Map;
public class WorkspaceSnapshotCheck {
 static AmuaModel current(frmMain app)throws Exception{java.lang.reflect.Field f=frmMain.class.getDeclaredField("curModel");f.setAccessible(true);return (AmuaModel)f.get(app);}
 public static void main(String[] args)throws Exception{
  try{SwingUtilities.invokeAndWait(()->{try{
   frmMain app=new frmMain("0.3.6");
   for(String fixture:args){app.openModel(new File(fixture));AmuaModel model=current(app);boolean dirty=model.unsavedChanges;int undo=model.actionStackUndo.size();
    Map<String,Object> before=WorkspaceSnapshot.capture(model);String xml=(String)before.get("xml");
    if(xml.contains(fixture)||!xml.contains("<Parameter>")||!xml.contains("<childIndices>"))throw new AssertionError("Incomplete or path-leaking snapshot");
    if(model.unsavedChanges!=dirty||model.actionStackUndo.size()!=undo)throw new AssertionError("Review modified user model");
    String old=model.name;model.name="Changed manual model";Map after=WorkspaceSnapshot.capture(model);if(before.get("sha256").equals(after.get("sha256")))throw new AssertionError("Content change not detected");model.name=old;
    if(!before.get("sha256").equals(WorkspaceSnapshot.capture(model).get("sha256")))throw new AssertionError("Snapshot not stable");
    System.out.println("PASS read-only full "+before.get("model_type")+" workspace snapshot, fields/order/settings, transient path exclusion, content-change detection");
   }
   System.exit(0);
  }catch(Throwable e){e.printStackTrace();System.exit(1);}});}catch(Throwable e){e.printStackTrace();System.exit(1);}
 }
}
