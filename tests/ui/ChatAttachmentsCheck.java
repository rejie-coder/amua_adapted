package v21;

import javax.swing.*;
import javax.swing.text.DefaultEditorKit;
import java.awt.*;
import java.awt.datatransfer.*;
import java.awt.event.*;
import java.awt.image.BufferedImage;
import java.nio.file.*;
import java.util.*;
import java.util.List;

/** Real Swing transfer handlers with a private clipboard; no desktop clipboard or service. */
public class ChatAttachmentsCheck {
    interface Checked{void run()throws Exception;}
    static WorkflowPanel ui;
    static void edt(Checked action)throws Exception{SwingUtilities.invokeAndWait(()->{try{action.run();}catch(Exception e){throw new RuntimeException(e);}});}
    static void check(boolean yes,String message){if(!yes)throw new AssertionError(message);}
    static Transferable payload(DataFlavor flavor,Object data){return new Transferable(){public DataFlavor[] getTransferDataFlavors(){return new DataFlavor[]{flavor};}public boolean isDataFlavorSupported(DataFlavor f){return flavor.equals(f);}public Object getTransferData(DataFlavor f)throws UnsupportedFlavorException{if(!isDataFlavorSupported(f))throw new UnsupportedFlavorException(f);return data;}};}
    static boolean paste(Transferable value){return ui.message.getTransferHandler().importData(ui.message,value);}
    static boolean drop(Transferable value){return ui.message.getTransferHandler().importData(new TransferHandler.TransferSupport(ui.message,value));}
    static void waitImage()throws Exception{long end=System.nanoTime()+15_000_000_000L;boolean[] pending={true};while(pending[0]&&System.nanoTime()<end){edt(()->pending[0]=ui.attachments.pending>0);if(pending[0])Thread.sleep(20);}check(!pending[0],"Pasted image worker did not finish");}
    public static void main(String[] args)throws Exception{
        try{
            Path folder=Files.createTempDirectory(Paths.get(System.getProperty("amua.support")),"attachments-");Path csv=folder.resolve("Decision inputs ü.csv");Files.write(csv,"p,cost,qaly\n0.7,1000,2.0\n".getBytes("UTF-8"));Path text=folder.resolve("Context note.txt");Files.write(text,"horizon unknown".getBytes("UTF-8"));
            edt(()->{
                ui=new WorkflowPanel(ModelChatControllerCheck.host());ui.stop();Clipboard clipboard=new Clipboard("private attachment test");
                ui.message.setText("hello world");ui.message.select(0,5);ui.message.getTransferHandler().exportToClipboard(ui.message,clipboard,TransferHandler.COPY);check("hello".equals(clipboard.getData(DataFlavor.stringFlavor)),"Text copy broke");check("hello world".equals(ui.message.getText()),"Copy cut text");
                ui.message.getTransferHandler().exportToClipboard(ui.message,clipboard,TransferHandler.MOVE);check(" world".equals(ui.message.getText()),"Text cut broke");check(paste(clipboard.getContents(null)),"Text paste rejected");check("hello world".equals(ui.message.getText()),"Text paste changed contents");
                int mask=System.getProperty("os.name","").toLowerCase(Locale.ROOT).contains("mac")?InputEvent.META_DOWN_MASK:InputEvent.CTRL_DOWN_MASK;
                check(DefaultEditorKit.pasteAction.equals(ui.message.getInputMap().get(KeyStroke.getKeyStroke(KeyEvent.VK_V,mask))),"Platform paste shortcut missing");check(ui.message.getComponentPopupMenu()!=null&&ui.conversation.getComponentPopupMenu()!=null,"Copy/paste popup missing");
                ui.history.add(Collections.singletonMap("role","assistant"));ui.lastRequest=new LinkedHashMap<>();ui.pendingChat=new LinkedHashMap<>();ui.applyProposal.setEnabled(true);
                check(drop(payload(DataFlavor.javaFileListFlavor,Arrays.asList(csv.toFile(),text.toFile()))),"File list drop failed");
                check(ui.paths.size()==2&&ui.paths.contains(csv.toString()),"Dropped source names lost");check("hello world".equals(ui.message.getText()),"Drop overwrote question text");
                check(ui.project==null&&ui.selectionPlan==null&&ui.history.isEmpty()&&ui.lastRequest==null&&ui.pendingChat==null&&!ui.applyProposal.isEnabled(),"Attachment retained stale approval/proposal");check(ui.process==null&&!ui.activityTimer.isRunning(),"Drop automatically sent a request");
                check(paste(payload(DataFlavor.javaFileListFlavor,Arrays.asList(csv.toFile()))),"Copied file paste failed");check(ui.paths.size()==2,"Duplicate file added twice");
                Path other=folder.resolve("Other source.csv");Files.write(other,"p\n0.3".getBytes("UTF-8"));check(drop(payload(ChatAttachments.URI_LIST,"# local file\r\n"+other.toUri()+"\r\n")),"Local file URI drop failed");check(ui.paths.size()==3,"Local URI attachment missing");
                check(!drop(payload(ChatAttachments.URI_LIST,"https://example.invalid/source.csv")),"Web URL became a local attachment");check(!drop(payload(DataFlavor.javaFileListFlavor,Arrays.asList(folder.toFile()))),"Folder silently expanded");
                Path unsupported=folder.resolve("program.exe");Files.write(unsupported,new byte[]{1});check(!paste(payload(DataFlavor.javaFileListFlavor,Arrays.asList(unsupported.toFile()))),"Unsupported file accepted");
                Path link=folder.resolve("shortcut.csv");Files.createSymbolicLink(link,csv);check(!drop(payload(DataFlavor.javaFileListFlavor,Arrays.asList(link.toFile()))),"Symlink accepted");
                Path large=folder.resolve("Oversized.txt");try(java.io.RandomAccessFile file=new java.io.RandomAccessFile(large.toFile(),"rw")){file.setLength(ChatAttachments.MAX_FILE+1);}check(!drop(payload(DataFlavor.javaFileListFlavor,Arrays.asList(large.toFile()))),"Oversized file accepted");
                check(!drop(payload(DataFlavor.javaFileListFlavor,Collections.nCopies(21,csv.toFile()))),"Unbounded file list accepted");check(ui.paths.size()==3,"Rejected attachments changed the source list");
                BufferedImage image=new BufferedImage(4,3,BufferedImage.TYPE_INT_ARGB);image.setRGB(2,1,0xff12ab34);check(paste(payload(DataFlavor.imageFlavor,image)),"Screenshot paste rejected");check(ui.attachments.pending==1,"Image encoding is not asynchronous");ui.send();check(ui.lastRequest==null&&ui.process==null,"Send raced an unfinished image");
            });
            waitImage();
            edt(()->{
                check(ui.paths.size()==4,"Pasted screenshot was not attached");Path png=Paths.get(ui.paths.get(3));BufferedImage decoded=javax.imageio.ImageIO.read(png.toFile());check(decoded.getWidth()==4&&decoded.getHeight()==3&&decoded.getRGB(2,1)==0xff12ab34,"Screenshot pixels changed");
                check(Files.getPosixFilePermissions(png).equals(java.nio.file.attribute.PosixFilePermissions.fromString("rw-------")),"Screenshot is not private to the user");
                check(((List)ui.chatRequest("Create a tree").get("paths")).contains(png.toString()),"Pasted image absent from normal outgoing request path");check(ui.process==null,"Image completion automatically sent a request");
                ui.setSize(340,600);HardeningControllerCheck.layout(ui);Point location=SwingUtilities.convertPoint(ui.message,0,0,ui);check(location.y>=0&&location.y+ui.message.getHeight()<=600,"Chat entry left the small sidebar");
                BufferedImage view=new BufferedImage(340,600,BufferedImage.TYPE_INT_ARGB);Graphics2D graphics=view.createGraphics();ui.printAll(graphics);graphics.dispose();javax.imageio.ImageIO.write(view,"png",Paths.get(args[0]).toFile());
                BufferedImage abandoned=new BufferedImage(3,2,BufferedImage.TYPE_INT_ARGB);check(paste(payload(DataFlavor.imageFlavor,abandoned)),"Second image paste rejected");ui.clearSourceAttachments();check(ui.paths.isEmpty(),"Clear did not remove attachments");
            });
            waitImage();edt(()->{check(ui.paths.isEmpty(),"Cleared screenshot reappeared after worker completion");check(ui.process==null&&ui.lastRequest==null,"Clear triggered inference");});
            System.out.println("PASS chat clipboard/drop: text copy/cut/paste, platform shortcut and menus, file-list and local URI imports, screenshot pixel/privacy preservation, asynchronous image preparation, outgoing request inclusion, deduplication, stale approval invalidation, no auto-send, limits/type/symlink rejection, Clear discards late image, 340x600 layout");System.exit(0);
        }catch(Throwable error){error.printStackTrace();System.exit(1);}
    }
}
