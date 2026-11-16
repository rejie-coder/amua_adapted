import base.*;import java.nio.file.*;import java.util.*;
public class AtomicSaveCheck{
 public static void main(String[] args)throws Exception{
  Path dir=Files.createTempDirectory("amua-save-check-").toRealPath();Path p=dir.resolve("test.amua");
  AmuaModel model=new AmuaModel();model.name="old";model.meta=new main.Metadata("0.3.6");
  AtomicModelSave.save(model,p,false);byte[] old=Files.readAllBytes(p);int checks=1;
  for(final String boundary:new String[]{"locked","staged","verified","backed-up"}){
   model.name="new";
   try{AtomicModelSave.save(model,p,true,new AtomicModelSave.Fault(){public void at(String b)throws java.io.IOException{if(b.equals(boundary))throw new java.io.IOException("injected");}});throw new AssertionError(boundary);}
   catch(java.io.IOException expected){}
   if(!Arrays.equals(old,Files.readAllBytes(p)))throw new AssertionError("prior generation lost at "+boundary);checks++;
  }
  model.name="new";AtomicModelSave.save(model,p,true);if(!Arrays.equals(old,Files.readAllBytes(dir.resolve("test.amua.previous"))))throw new AssertionError("backup mismatch");checks++;
  byte[] saved=Files.readAllBytes(p);Files.write(p,"external".getBytes("UTF-8"));
  try{AtomicModelSave.save(model,p,true);throw new AssertionError("external update accepted");}catch(java.io.IOException expected){}checks++;
  Files.write(p,saved);Path linked=dir.resolve("linked.amua");Files.createSymbolicLink(linked,p);
  try{AtomicModelSave.save(model,linked,true);throw new AssertionError("symlink accepted");}catch(java.io.IOException expected){}checks++;
  try{AtomicModelSave.save(new AmuaModel(),p,false);throw new AssertionError("existing target overwritten");}catch(java.nio.file.FileAlreadyExistsException expected){}checks++;
  // Simulated post-publish failure leaves a fully parseable new generation plus old backup.
  AtomicModelSave.remember(model,p);model.name="published";
  try{AtomicModelSave.save(model,p,true,new AtomicModelSave.Fault(){public void at(String b)throws java.io.IOException{if(b.equals("published"))throw new java.io.IOException("injected");}});throw new AssertionError();}catch(java.io.IOException expected){}
  javax.xml.bind.JAXBContext.newInstance(AmuaModel.class).createUnmarshaller().unmarshal(p.toFile());checks++;
  AtomicModelSave.remember(model,p);model.filepath=p.toString();model.unsavedChanges=false;Files.write(p,"external-after-open".getBytes("UTF-8"));model.saveModel();if(!model.unsavedChanges)throw new AssertionError("dirty flag cleared on failure");checks++;
  Path lockFile=dir.resolve("locked.amua.save-lock");try(java.nio.channels.FileChannel ch=java.nio.channels.FileChannel.open(lockFile,StandardOpenOption.CREATE,StandardOpenOption.WRITE);java.nio.channels.FileLock lock=ch.lock()){
   try{AtomicModelSave.save(model,dir.resolve("locked.amua"),false);throw new AssertionError("concurrent lock accepted");}catch(java.io.IOException expected){}checks++;
  }
  Path fresh=dir.resolve("fresh.amua");try{AtomicModelSave.save(model,fresh,false,new AtomicModelSave.Fault(){public void at(String b)throws java.io.IOException{if(b.equals("staged"))throw new java.io.IOException("new-file crash");}});throw new AssertionError();}catch(java.io.IOException expected){}if(Files.exists(fresh))throw new AssertionError("partial new target");checks++;
  Path entity=dir.resolve("entity.amua");Files.write(entity,"<?xml version='1.0'?><!DOCTYPE Model [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><Model><name>&x;</name></Model>".getBytes("UTF-8"));
  try{AtomicModelSave.read(entity);throw new AssertionError("external entity accepted");}catch(Exception expected){}checks++;
  System.out.println("PASS "+checks+" atomic save checks; "+dir);
 }
}
