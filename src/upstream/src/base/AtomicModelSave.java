package base;

import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import javax.xml.bind.*;
import javax.xml.parsers.SAXParserFactory;
import javax.xml.transform.sax.SAXSource;
import org.xml.sax.InputSource;
import org.xml.sax.XMLReader;

/** Candidate local-file save service. Caller captures/serializes mutable models on EDT. */
public final class AtomicModelSave {
    private static final Map<AmuaModel, Binding> bindings=new WeakHashMap<AmuaModel,Binding>();
    public interface Fault { void at(String boundary) throws IOException; }
    private static final Fault NONE=new Fault(){public void at(String b){}};
    private static final class Binding { Path path; byte[] hash; Binding(Path p,byte[] h){path=p;hash=h;} }
    public static synchronized void remember(AmuaModel model,Path path) throws IOException {
        Path p=path.toAbsolutePath().normalize(); rejectSymlink(p);bindings.put(model,new Binding(p,hash(p)));
    }
    static byte[] hash(Path p)throws IOException {
        if(!Files.exists(p,LinkOption.NOFOLLOW_LINKS))return null;
        try {MessageDigest d=MessageDigest.getInstance("SHA-256");try(InputStream in=Files.newInputStream(p)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)d.update(b,0,n);}return d.digest();}
        catch(NoSuchAlgorithmException e){throw new IOException(e);}
    }
    static void rejectSymlink(Path p)throws IOException {
        Path c=p;while(c!=null){if(Files.isSymbolicLink(c))throw new IOException("Save requires a local path without symbolic links; choose Save Copy.");c=c.getParent();}
    }
    public static void save(AmuaModel model,Path path,boolean replace)throws Exception {save(model,path,replace,NONE);}
    public static synchronized void save(AmuaModel model,Path path,boolean replace,Fault fault)throws Exception {
        if(model.mainForm!=null&&!java.awt.EventQueue.isDispatchThread())throw new IOException("Model save must capture data on the event thread.");
        Path target=path.toAbsolutePath().normalize();rejectSymlink(target);
        if(!Files.isDirectory(target.getParent()))throw new IOException("Save directory does not exist.");
        Path lockPath=target.resolveSibling(target.getFileName()+".save-lock");rejectSymlink(lockPath);
        try(FileChannel channel=FileChannel.open(lockPath,StandardOpenOption.CREATE,StandardOpenOption.WRITE)){
            FileLock lock;
            try{lock=channel.tryLock();}catch(OverlappingFileLockException e){throw new IOException("Another writer is saving this model.");}
            if(lock==null)throw new IOException("Another writer is saving this model.");
            try {
                byte[] before=hash(target);Binding known=bindings.get(model);
                if(before!=null&&!replace)throw new FileAlreadyExistsException(target.toString());
                if(known!=null&&known.path.equals(target)&&!Arrays.equals(known.hash,before))throw new IOException("Model changed outside this window; use Save Copy.");
                fault.at("locked");
                Path temporary=Files.createTempFile(target.getParent(),".amua-stage-",".tmp"),backupTemp=null;
                try {
                    model.meta.update();JAXBContext context=JAXBContext.newInstance(AmuaModel.class);
                    Marshaller m=context.createMarshaller();m.setProperty(Marshaller.JAXB_FORMATTED_OUTPUT,true);m.setProperty(Marshaller.JAXB_ENCODING,"UTF-8");
                    try(FileOutputStream out=new FileOutputStream(temporary.toFile())){m.marshal(model,out);out.flush();out.getFD().sync();}
                    fault.at("staged");validate(context,temporary);byte[] expected=hash(temporary);fault.at("verified");
                    if(!Arrays.equals(before,hash(target)))throw new IOException("Destination changed during save; use Save Copy.");
                    if(before!=null){
                        backupTemp=Files.createTempFile(target.getParent(),".amua-backup-",".tmp");Files.copy(target,backupTemp,StandardCopyOption.REPLACE_EXISTING);
                        try(FileChannel b=FileChannel.open(backupTemp,StandardOpenOption.WRITE)){b.force(true);}
                        validate(context,backupTemp);if(!Arrays.equals(before,hash(backupTemp)))throw new IOException("Backup verification failed.");
                        Path backup=target.resolveSibling(target.getFileName()+".previous");rejectSymlink(backup);
                        Files.move(backupTemp,backup,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);backupTemp=null;
                    }
                    fault.at("backed-up");
                    if(before==null){Files.createLink(target,temporary);Files.delete(temporary);}
                    else Files.move(temporary,target,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                    fault.at("published");
                    if(!Arrays.equals(expected,hash(target)))throw new IOException("Published model verification failed; recover previous generation.");
                    if(!System.getProperty("os.name","").toLowerCase(java.util.Locale.ROOT).startsWith("windows")){
                        try(FileChannel dir=FileChannel.open(target.getParent(),StandardOpenOption.READ)){dir.force(true);}
                    }
                    bindings.put(model,new Binding(target,expected));fault.at("durable");
                }finally{Files.deleteIfExists(temporary);if(backupTemp!=null)Files.deleteIfExists(backupTemp);}
            }finally{lock.release();}
        }
    }
    public static AmuaModel read(Path path)throws Exception {return validate(JAXBContext.newInstance(AmuaModel.class),path);}
    static AmuaModel validate(JAXBContext context,Path path)throws Exception {
        if(Files.size(path)>64L*1024*1024)throw new IOException("Model exceeds the 64 MiB supported XML input limit.");
        SAXParserFactory factory=SAXParserFactory.newInstance();factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities",false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities",false);
        XMLReader reader=factory.newSAXParser().getXMLReader();
        org.xml.sax.helpers.XMLFilterImpl bounded=new org.xml.sax.helpers.XMLFilterImpl(reader){
            int depth=0,elements=0;long characters=0;
            public void startElement(String uri,String local,String q,org.xml.sax.Attributes a)throws org.xml.sax.SAXException{
                if(++depth>200||++elements>250000)throw new org.xml.sax.SAXException("Model XML depth or element limit exceeded");
                super.startElement(uri,local,q,a);
            }
            public void endElement(String uri,String local,String q)throws org.xml.sax.SAXException{super.endElement(uri,local,q);depth--;}
            public void characters(char[] c,int start,int length)throws org.xml.sax.SAXException{
                characters+=length;if(characters>24L*1024*1024)throw new org.xml.sax.SAXException("Model text exceeds the 24 MiB supported limit");super.characters(c,start,length);
            }
        };
        try(InputStream in=Files.newInputStream(path)){Object value=context.createUnmarshaller().unmarshal(new SAXSource(bounded,new InputSource(in)));if(!(value instanceof AmuaModel))throw new IOException("Invalid staged model.");return (AmuaModel)value;}
    }
}
