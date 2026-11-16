package v21;
import gui.frmMain;
import base.AmuaModel;
import main.Console;
import javax.swing.SwingUtilities;
import java.io.File;
/** Isolated engine verification for a locally constructed scoped module. */
public final class ValidateModule {
 public static void main(String[] args)throws Exception{
  if(args.length!=2)System.exit(2);
  SwingUtilities.invokeAndWait(()->{try{
   frmMain app=new frmMain("0.3.6");app.openModel(new File(args[0]));
   java.lang.reflect.Field mf=frmMain.class.getDeclaredField("curModel");mf.setAccessible(true);AmuaModel model=(AmuaModel)mf.get(app);
   java.lang.reflect.Field cf=frmMain.class.getDeclaredField("console");cf.setAccessible(true);Console console=(Console)cf.get(app);
   if(model==null||!model.checkModel(console,true))throw new IllegalArgumentException("Engine validation rejected module");
   model.runModel(console,true);if(model.getStrategies()!=1)throw new IllegalArgumentException("Unexpected module scope");
   double actual=model.getStrategyEV(0,0),expected=Double.parseDouble(args[1]);if(!Double.isFinite(actual)||Math.abs(actual-expected)>0.0000001)throw new IllegalArgumentException("Arithmetic reconciliation failed");
   System.out.println("AMUA_VALIDATED "+actual);System.exit(0);
  }catch(Throwable error){System.out.println("AMUA_REJECTED");System.exit(1);}});
 }
}
