package v21;

import base.AmuaModel;
import gui.frmMain;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.swing.*;

/** Applies local schema-checked candidates as native models. Provider text never executes. */
public final class ModelChat {
    public static AmuaModel read(String xml)throws Exception{
        Path directory=Paths.get(System.getProperty("amua.support"));Files.createDirectories(directory);
        Path file=Files.createTempFile(directory,"candidate-",".amua");
        try{Files.write(file,xml.getBytes(StandardCharsets.UTF_8));return base.AtomicModelSave.read(file);}finally{Files.deleteIfExists(file);}
    }
    public static void apply(frmMain app,String xml,AmuaModel target,String expectedHash,boolean replace)throws Exception{
        if(!SwingUtilities.isEventDispatchThread())throw new IllegalStateException("Apply on the event thread");
        AmuaModel candidate=read(xml);
        if(candidate.type!=0||candidate.tree==null||candidate.tree.nodes.size()<2)throw new IllegalArgumentException("Invalid native decision tree");
        if(replace){
            Map current=WorkspaceSnapshot.capture(target);
            if(current==null||!Objects.equals(current.get("sha256"),expectedHash))throw new IllegalStateException("The target changed. Send a fresh request; this proposal has not been applied.");
        }
        app.applyWorkflowCandidate(candidate,target,replace);
    }
    public static Map state(AmuaModel model){
        if(model==null||model.type!=0||model.tree.nodes.isEmpty())return null;
        try{String notes=model.tree.nodes.get(0).notes;String marker="AMUA_CHAT_V1\n";int at=notes==null?-1:notes.indexOf(marker);if(at<0)return null;
            javax.script.ScriptEngine engine=new javax.script.ScriptEngineManager().getEngineByName("nashorn");engine.put("payload",notes.substring(at+marker.length()));return (Map)engine.eval("Java.asJSONCompatible(JSON.parse(payload))");
        }catch(Exception error){return null;}
    }
    public static AmuaModel withoutSourceInventory(AmuaModel source)throws Exception{
        Map snapshot=WorkspaceSnapshot.capture(source);AmuaModel copy=read((String)snapshot.get("xml"));
        if(copy.type==0&&!copy.tree.nodes.isEmpty()){
            String notes=copy.tree.nodes.get(0).notes,marker="AMUA_CHAT_V1\n";int at=notes==null?-1:notes.indexOf(marker);
            if(at>=0){javax.script.ScriptEngine engine=new javax.script.ScriptEngineManager().getEngineByName("nashorn");engine.put("payload",notes.substring(at+marker.length()));
                String clean=(String)engine.eval("var s=JSON.parse(payload); delete s.evidence; if(s.proposal && s.proposal.input_review) s.proposal.input_review.forEach(function(i){delete i.cited_values;}); JSON.stringify(s)");
                copy.tree.nodes.get(0).notes=notes.substring(0,at)+marker+clean;}
        }
        return copy;
    }
}
