package v21;

import javax.swing.*;
import javax.swing.text.DefaultEditorKit;
import java.awt.*;
import java.awt.datatransfer.*;
import java.awt.event.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.net.URI;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import java.util.List;

/** Chat-only clipboard/drop handling. Attaching never starts inference. */
final class ChatAttachments extends TransferHandler {
    static final long MAX_FILE=25L*1024*1024, MAX_TOTAL=100L*1024*1024;
    static final DataFlavor URI_LIST;
    static {try{URI_LIST=new DataFlavor("text/uri-list;class=java.lang.String");}catch(ClassNotFoundException e){throw new ExceptionInInitializerError(e);}}
    final WorkflowPanel ui;
    final TransferHandler text;
    final JLabel label=new JLabel("Paste or drop images / files here");
    int generation, pending;
    ChatAttachments(WorkflowPanel ui){
        this.ui=ui;text=ui.message.getTransferHandler();ui.message.setTransferHandler(this);
        installTextActions(ui.message,true);installTextActions(ui.conversation,false);
        ui.message.setToolTipText("Type text, paste a screenshot, or drop source files. Attachments wait for Send and outgoing review.");
        ui.message.getComponentPopupMenu().addSeparator();JMenuItem clear=new JMenuItem("Clear attachments");clear.addActionListener(e->ui.clearSourceAttachments());ui.message.getComponentPopupMenu().add(clear);
    }
    static void installTextActions(javax.swing.text.JTextComponent field,boolean editable){
        int mask=System.getProperty("os.name","").toLowerCase(Locale.ROOT).contains("mac")?InputEvent.META_DOWN_MASK:InputEvent.CTRL_DOWN_MASK;
        field.getInputMap().put(KeyStroke.getKeyStroke(KeyEvent.VK_C,mask),DefaultEditorKit.copyAction);
        field.getInputMap().put(KeyStroke.getKeyStroke(KeyEvent.VK_A,mask),DefaultEditorKit.selectAllAction);
        JPopupMenu menu=new JPopupMenu();
        if(editable){field.getInputMap().put(KeyStroke.getKeyStroke(KeyEvent.VK_X,mask),DefaultEditorKit.cutAction);field.getInputMap().put(KeyStroke.getKeyStroke(KeyEvent.VK_V,mask),DefaultEditorKit.pasteAction);}
        for(String name:editable?new String[]{DefaultEditorKit.cutAction,DefaultEditorKit.copyAction,DefaultEditorKit.pasteAction,DefaultEditorKit.selectAllAction}:new String[]{DefaultEditorKit.copyAction,DefaultEditorKit.selectAllAction}){
            Action action=field.getActionMap().get(name);if(action!=null){JMenuItem item=new JMenuItem(action);item.setText(name.equals(DefaultEditorKit.cutAction)?"Cut":name.equals(DefaultEditorKit.copyAction)?"Copy":name.equals(DefaultEditorKit.pasteAction)?"Paste":"Select all");menu.add(item);}
        }
        field.setComponentPopupMenu(menu);
    }
    void reset(){generation++;refresh();}
    void refresh(){label.setText(pending>0?"Preparing pasted image…":ui.paths.isEmpty()?"Paste or drop images / files here":ui.paths.size()+" source attachment(s) · review before Send");label.setToolTipText(String.join("\n",ui.paths));}
    boolean attachment(DataFlavor[] flavors){for(DataFlavor flavor:flavors)if(flavor.equals(DataFlavor.javaFileListFlavor)||flavor.equals(DataFlavor.imageFlavor)||flavor.equals(URI_LIST))return true;return false;}
    public boolean canImport(TransferSupport support){
        boolean yes=attachment(support.getDataFlavors())||text!=null&&text.canImport(support);
        if(yes&&support.isDrop()){if((support.getSourceDropActions()&COPY)==0)return false;support.setDropAction(COPY);}return yes;
    }
    public boolean canImport(JComponent component,DataFlavor[] flavors){return attachment(flavors)||text!=null&&text.canImport(component,flavors);}
    public boolean importData(TransferSupport support){if(!canImport(support))return false;return attachment(support.getDataFlavors())?importAttachment(support.getTransferable()):text!=null&&text.importData(support);}
    public boolean importData(JComponent component,Transferable value){return attachment(value.getTransferDataFlavors())?importAttachment(value):text!=null&&text.importData(component,value);}
    public int getSourceActions(JComponent component){return text==null?NONE:text.getSourceActions(component);}
    public void exportToClipboard(JComponent component,Clipboard clipboard,int action){if(text!=null)text.exportToClipboard(component,clipboard,action);}
    public void exportAsDrag(JComponent component,InputEvent event,int action){if(text!=null)text.exportAsDrag(component,event,action);}
    boolean importAttachment(Transferable value){
        try{
            if(value.isDataFlavorSupported(DataFlavor.javaFileListFlavor)){
                Object raw=value.getTransferData(DataFlavor.javaFileListFlavor);if(!(raw instanceof List))throw new IOException("Clipboard file list is invalid.");
                List<Path> files=new ArrayList<>();for(Object item:(List)raw){if(!(item instanceof File))throw new IOException("Clipboard file list is invalid.");files.add(((File)item).toPath());}attach(files);return true;
            }
            if(value.isDataFlavorSupported(DataFlavor.imageFlavor)){
                if(pending>0)throw new IOException("Wait for the pasted image to finish preparing.");
                Object raw=value.getTransferData(DataFlavor.imageFlavor);if(!(raw instanceof Image))throw new IOException("Clipboard image is unreadable.");
                if(ui.paths.size()>=20)throw new IOException("At most 20 source attachments are allowed. Clear attachments first.");
                Image image=(Image)raw;int version=generation;pending++;refresh();
                new SwingWorker<Path,Void>(){
                    protected Path doInBackground()throws Exception{return saveImage(image);}
                    protected void done(){pending--;Path path=null;try{path=get();if(version!=generation){Files.deleteIfExists(path);return;}attach(Collections.singletonList(path));}catch(Exception error){if(path!=null)try{Files.deleteIfExists(path);}catch(IOException ignored){}if(version==generation)failure(error);}finally{refresh();}}
                }.execute();return true;
            }
            if(value.isDataFlavorSupported(URI_LIST)){
                List<Path> files=new ArrayList<>();for(String line:String.valueOf(value.getTransferData(URI_LIST)).split("\\r?\\n")){line=line.trim();if(line.isEmpty()||line.startsWith("#"))continue;URI uri=new URI(line);if(!"file".equalsIgnoreCase(uri.getScheme())||uri.getAuthority()!=null&&!uri.getAuthority().isEmpty())throw new IOException("Drop local files, not web links or remote file URLs.");files.add(Paths.get(uri));}attach(files);return true;
            }
        }catch(Exception error){failure(error);}return false;
    }
    void failure(Exception error){Throwable cause=error.getCause()==null?error:error.getCause();ui.append("Attachment not added: "+(cause instanceof IOException?cause.getMessage():"Clipboard or file content could not be read."));}
    void attach(List<Path> incoming)throws IOException{
        if(incoming.isEmpty()||incoming.size()>20)throw new IOException("Select between 1 and 20 ordinary source files.");
        LinkedHashSet<String> selected=new LinkedHashSet<>(ui.paths);long total=0;
        for(Path path:incoming){path=path.toAbsolutePath().normalize();
            for(Path part=path;part!=null;part=part.getParent())if(Files.isSymbolicLink(part))throw new IOException("Select a resolved ordinary file; symlinks are unsupported.");
            if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)||!Files.isReadable(path))throw new IOException("Drop readable files. Use Select files / folder for folders.");
            if(!path.getFileName().toString().toLowerCase(Locale.ROOT).matches(".*\\.(png|jpg|jpeg|xlsx|docx|pdf|html|htm|txt|csv|md|rst|tsv|json)"))throw new IOException("Unsupported source type: "+path.getFileName());
            if(Files.size(path)>MAX_FILE)throw new IOException("A source attachment exceeds 25 MiB.");selected.add(path.toString());
        }
        if(selected.size()>20)throw new IOException("At most 20 source attachments are allowed. Clear attachments first.");
        for(String path:selected)if(Files.isRegularFile(Paths.get(path))){total+=Files.size(Paths.get(path));if(total>MAX_TOTAL)throw new IOException("Source attachments exceed 100 MiB.");}
        if(selected.size()==ui.paths.size()){ui.append("These files are already attached.");return;}
        ui.stop();ui.paths.clear();ui.paths.addAll(selected);ui.sources.setText(String.join("\n",ui.paths));ui.project=null;ui.selectionPlan=null;ui.history.clear();ui.lastRequest=null;ui.lastHelper=null;ui.pendingChat=null;ui.applyProposal.setEnabled(false);ui.lastProposalFailure=null;
        refresh();ui.status.setText("Attachments ready · press Send");ui.append("Added "+incoming.size()+" source attachment(s). Review the source list; press Send when ready. Nothing was sent.");
    }
    Path saveImage(Image image)throws IOException{
        int width=image.getWidth(null),height=image.getHeight(null);if(width<1||height<1){ImageIcon loaded=new ImageIcon(image);width=loaded.getIconWidth();height=loaded.getIconHeight();}
        if(width<1||height<1||(long)width*height>40000000L)throw new IOException("Clipboard image is unreadable or exceeds 40 million pixels.");
        Path folder=Paths.get(System.getProperty("amua.support"),"chat-attachments");Files.createDirectories(folder);
        try{Files.setPosixFilePermissions(folder,PosixFilePermissions.fromString("rwx------"));}catch(UnsupportedOperationException ignored){}
        long cached=0;try(DirectoryStream<Path> entries=Files.newDirectoryStream(folder)){for(Path entry:entries)if(Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS))cached+=Files.size(entry);}
        if(cached>=MAX_TOTAL)throw new IOException("Pasted-image storage is full (100 MiB). Remove unused files from "+folder+".");
        BufferedImage bitmap=new BufferedImage(width,height,BufferedImage.TYPE_INT_ARGB);Graphics2D graphics=bitmap.createGraphics();try{if(!graphics.drawImage(image,0,0,null))throw new IOException("Clipboard image has not finished loading.");}finally{graphics.dispose();}
        Path saved=Files.createTempFile(folder,"Pasted image - ",".png");boolean success=false;
        try{
            try{Files.setPosixFilePermissions(saved,PosixFilePermissions.fromString("rw-------"));}catch(UnsupportedOperationException ignored){}
            final long limit=Math.min(MAX_FILE,MAX_TOTAL-cached);
            try(OutputStream file=Files.newOutputStream(saved);OutputStream bounded=new FilterOutputStream(file){long written;public void write(int b)throws IOException{if(++written>limit)throw new IOException("Pasted image exceeds the attachment storage limit.");out.write(b);}public void write(byte[] b,int off,int len)throws IOException{written+=len;if(written>limit)throw new IOException("Pasted image exceeds the attachment storage limit.");out.write(b,off,len);}}){if(!javax.imageio.ImageIO.write(bitmap,"png",bounded))throw new IOException("PNG encoding is unavailable.");}
            success=true;return saved;
        }finally{if(!success)Files.deleteIfExists(saved);}
    }
}
