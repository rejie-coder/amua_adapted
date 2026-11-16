package v21;

import gui.frmMain;
import javax.swing.*;
import javax.swing.tree.*;
import javax.script.*;
import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/** Candidate workflow UI. Proposals remain isolated from manual calculation tabs. */
public final class WorkflowPanel extends JPanel {
    final frmMain app;
    final JCheckBox includeWorkspace=new JCheckBox("Include current workspace model",true);
    final JCheckBox includeEmbeddedEvidence=new JCheckBox("Include saved source inventory",false);
    final JLabel status=new JLabel("Checking saved ChatGPT connection…");
    final JProgressBar activity=new JProgressBar();
    final javax.swing.Timer activityTimer=new javax.swing.Timer(250,e->updateActivity());
    long activityStarted;
    String activeAction;
    volatile long lastModelProgressNanos=System.nanoTime();
    volatile long lastModelProgressSequence;
    int activeModelIdleSeconds=180;


    final JTextArea conversation=new JTextArea(), message=new JTextArea(4,20), sources=new JTextArea(3,20);
    final List<String> paths=new ArrayList<>();
    final List<Map<String,Object>> history=new ArrayList<>();
    final AtomicLong epoch=new AtomicLong();
    final String budgetSession=UUID.randomUUID().toString();
    volatile Process process;
    final Object processLock=new Object();
    Map<String,Object> project;
    Map<String,Object> selectionPlan;
    final JCheckBox includeSubfolders=new JCheckBox("Include subfolders",false);
    JSplitPane split;
    JSplitPane consolePane;
    final java.util.prefs.Preferences preferences=java.util.prefs.Preferences.userRoot().node("local/rejie/amua/v21/layout");
    JPanel original;
    JButton retry;
    JButton applyProposal;
    ChatAttachments attachments;
    Map<String,Object> lastRequest;
    String lastHelper;
    Map<String,Object> pendingChat;
    Map<String,Object> pendingChatRequest;
    base.AmuaModel chatTarget;
    String chatTargetHash;
    base.AmuaModel pendingTarget;
    String pendingTargetHash;
    boolean outlineCreated;
    base.AmuaModel outlineTarget;
    String outlineTargetHash;
    String lastProposalFailure;

    public static void install(frmMain app) { new WorkflowPanel(app); }
    WorkflowPanel(frmMain app) {
        this.app=app;
        Runtime.getRuntime().addShutdownHook(new Thread(()->{Process child=process;if(child!=null){child.destroy();try{if(!child.waitFor(2500,java.util.concurrent.TimeUnit.MILLISECONDS))child.destroyForcibly();}catch(InterruptedException ignored){Thread.currentThread().interrupt();}}},"Amua workflow shutdown"));
        includeWorkspace.addActionListener(e->{stop();lastRequest=null;lastHelper=null;history.clear();});
        includeEmbeddedEvidence.addActionListener(e->{stop();lastRequest=null;lastHelper=null;history.clear();});
        includeSubfolders.addActionListener(e->{stop();selectionPlan=null;project=null;lastRequest=null;lastHelper=null;history.clear();append("Folder scope changed. Inspect sources again to read the new selection.");});
        setLayout(new BorderLayout(6,6)); setBorder(BorderFactory.createEmptyBorder(10,10,10,10));
        setPreferredSize(new Dimension(340,600)); setMinimumSize(new Dimension(280,200));
        JPanel top=new JPanel(); top.setLayout(new BoxLayout(top,BoxLayout.Y_AXIS));
        JLabel title=new JLabel("AI Workflow"); title.setFont(title.getFont().deriveFont(Font.BOLD,18));top.add(title); top.add(status);
        activity.setStringPainted(true);activity.setString("Idle");activity.setPreferredSize(new Dimension(300,18));activity.setMaximumSize(new Dimension(Integer.MAX_VALUE,18));activity.setVisible(false);activity.getAccessibleContext().setAccessibleName("AI Workflow activity");top.add(activity);
        JPanel connection=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));
        button(connection,text("continue_with_chatgpt"),()->provider("accounts"));button(connection,"Accounts…",()->provider("accounts"));top.add(connection);
        JPanel connectionTools=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));button(connectionTools,text("status"),()->provider("status"));button(connectionTools,text("disconnect"),()->{stop();history.clear();provider("logout");});button(connectionTools,"Manage usage",()->{try{java.awt.Desktop.getDesktop().browse(new java.net.URI("https://chatgpt.com/settings/usage"));}catch(Exception error){append("Open chatgpt.com/settings/usage in your browser to manage plan usage.");}});top.add(connectionTools);
        JPanel select=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));button(select,text("select_files_folder"),this::select);button(select,text("clear"),this::clearSourceAttachments);top.add(select);JPanel folderControls=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));folderControls.add(includeSubfolders);button(folderControls,"Continue folder reading",()->{if(selectionPlan==null){beginFolderRead(null);return;}List entries=(List)selectionPlan.get("entries");for(int i=0;i<entries.size();i++)if("pending".equals(((Map)entries.get(i)).get("status"))){readFolderBatch(i,null);return;}append("All planned folder entries have been attempted. Review failures or inspect again to make a fresh snapshot.");});top.add(folderControls);
        sources.setEditable(false);sources.setLineWrap(true);top.add(new JScrollPane(sources));
        JPanel operations=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));
        button(operations,text("inspect_sources"),()->workflow("intake"));button(operations,"Source inventory",this::showSourceRecords);button(operations,text("synthetic_example"),()->invoke("workflow",req("synthetic")));top.add(operations);JPanel workspaceControls=new JPanel(new BorderLayout());workspaceControls.add(includeWorkspace,BorderLayout.NORTH);button(workspaceControls,"Review workspace",()->{includeWorkspace.setSelected(true);message.setText("Review the current workspace model. Identify missing branches, invalid or unsupported inputs, assumptions, and useful improvements. Give suggestions for my review without changing or running the model.");send();});top.add(workspaceControls);
        JPanel persistence=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));button(persistence,text("open_project"),()->workflow("open"));button(persistence,text("save_project"),()->workflow("save"));top.add(persistence);
        JPanel modelActions=new JPanel(new GridLayout(0,2,3,3));
        applyProposal=button(modelActions,"Apply tree proposal",this::applyChatProposal);applyProposal.setEnabled(false);
        button(modelActions,"Save model as…",this::saveChatModel);
        button(modelActions,"Questions",this::showChatQuestions);
        button(modelActions,"Review inputs…",this::reviewProposedInputs);
        button(modelActions,"Save shareable copy…",this::saveShareableCopy);
        top.add(includeEmbeddedEvidence);
        JPanel pdfActions=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));button(pdfActions,"Read PDF pages…",this::readPdfPages);top.add(pdfActions);
        button(modelActions,"Validate",()->analyseChat("validate",null));
        button(modelActions,"Run",()->analyseChat("run",null));
        button(modelActions,"Sensitivity…",this::sensitivityChat);top.add(modelActions);
        for(Component child:top.getComponents())if(child instanceof JComponent)((JComponent)child).setAlignmentX(Component.LEFT_ALIGNMENT);
        title.setHorizontalAlignment(SwingConstants.LEFT);status.setHorizontalAlignment(SwingConstants.LEFT);
        status.setMaximumSize(new Dimension(Integer.MAX_VALUE,status.getPreferredSize().height));
        top.remove(title);top.remove(status);top.remove(activity);
        JPanel sticky=new JPanel();sticky.setLayout(new BoxLayout(sticky,BoxLayout.Y_AXIS));sticky.add(title);sticky.add(status);sticky.add(activity);
        modelActions.remove(applyProposal);applyProposal.setAlignmentX(Component.LEFT_ALIGNMENT);sticky.add(applyProposal);
        for(Component child:top.getComponents())if(child instanceof JPanel&&((JPanel)child).getLayout() instanceof FlowLayout)((JPanel)child).setLayout(new GridLayout(0,2,3,3));
        top.setMinimumSize(new Dimension(0,0));
        for(Component child:top.getComponents())if(child instanceof JComponent){Dimension minimum=child.getMinimumSize();child.setMinimumSize(new Dimension(0,minimum.height));}
        compactControlFonts(top);
        JScrollPane controlScroll=new JScrollPane(top);controlScroll.setPreferredSize(new Dimension(320,310));controlScroll.getVerticalScrollBar().setUnitIncrement(20);controlScroll.setHorizontalScrollBarPolicy(ScrollPaneConstants.HORIZONTAL_SCROLLBAR_NEVER);
        JPanel controls=new JPanel(new BorderLayout(0,6));controls.add(sticky,BorderLayout.NORTH);controls.add(controlScroll,BorderLayout.CENTER);add(controls,BorderLayout.NORTH);
        conversation.setEditable(false); conversation.setLineWrap(true); conversation.setWrapStyleWord(true);
        conversation.setText("Select sources to inventory them locally. Review outgoing material before sending to ChatGPT. Chat builds editable native trees. Unknown inputs become questions and block calculations until answered.\n");add(new JScrollPane(conversation),BorderLayout.CENTER);
        JPanel bottom=new JPanel(new BorderLayout(3,3));attachments=new ChatAttachments(this);JPanel composeHeader=new JPanel(new GridLayout(0,1));composeHeader.add(new JLabel("Situation / question"));composeHeader.add(attachments.label);bottom.add(composeHeader,BorderLayout.NORTH);message.setLineWrap(true);message.setWrapStyleWord(true);bottom.add(new JScrollPane(message),BorderLayout.CENTER);
        JPanel send=new JPanel(new FlowLayout(FlowLayout.LEFT,3,3));button(send,text("send"),this::send);button(send,text("stop"),this::stop);retry=button(send,text("retry"),this::retryLast);bottom.add(send,BorderLayout.SOUTH);add(bottom,BorderLayout.SOUTH);
        original=(JPanel)app.frmMain.getContentPane();split=new JSplitPane(JSplitPane.HORIZONTAL_SPLIT,this,original);split.setResizeWeight(0);split.setDividerLocation(340);split.setOneTouchExpandable(true);app.frmMain.setContentPane(split);
        JMenu menu=new JMenu(text("ai_workflow"));JMenuItem toggle=new JMenuItem(text("show_hide_sidebar"));toggle.addActionListener(e->{boolean show=!isVisible();setVisible(show);split.setDividerLocation(show?340:0);});menu.add(toggle);
        JMenuItem layout=new JMenuItem(text("balance_current_tree"));layout.addActionListener(e->balance());menu.add(layout);
        JCheckBoxMenuItem automatic=new JCheckBoxMenuItem(text("automatically_balance_edits_current_tree"));automatic.addActionListener(e->{if(model()!=null&&model().type==0){model().panelTree.automaticLayout=automatic.isSelected();if(automatic.isSelected())balance();}});menu.add(automatic);
        JMenuItem reset=new JMenuItem(text("reset_zoom"));reset.addActionListener(e->{if(model()!=null){model().rescale(100);app.setZoomVal(100);}});menu.add(reset);
        JMenuItem fit=new JMenuItem("Fit Tree");fit.addActionListener(e->fit());menu.add(fit);
        JMenuItem consoleToggle=new JMenuItem("Show / hide console");consoleToggle.addActionListener(e->{if(consolePane!=null)consolePane.setDividerLocation(consolePane.getDividerLocation()>consolePane.getHeight()-60?0.82:1.0);});menu.add(consoleToggle);
        JMenuItem waitSetting=new JMenuItem("AI stall timeout…");waitSetting.addActionListener(e->chooseModelStallTimeout());menu.add(waitSetting);
        JMenuItem credit=new JMenuItem(text("version_2_1_credits_and_capability_status"));credit.addActionListener(e->JOptionPane.showMessageDialog(app.frmMain,"Amua (ReyJay) V 3.2.4 - Engine 0.3.6\nAdapted and developed by Dr. Rejinten Jayawardhana.\nBased on the original Amua software by Zachary J. Ward.\nGPLv3-or-later; original notices retained.\n\nLocal intake: XLSX, DOCX, text PDFs, saved HTML, text/CSV and images.\nScanned PDFs need OCR; legacy DOC/XLS are unsupported.\nFolder reading is progressive, with visible failures and limits.\nChat receives a consistent snapshot; changes require review and remain undoable.\nChat proposes native editable trees; unresolved scientific questions block calculations. See the version test report for measured coverage.\nSee TEST_REPORT.md for measured coverage and remaining gates."));menu.add(credit);
        JMenuBar bar=app.frmMain.getJMenuBar();int index=Math.max(0,bar.getMenuCount()-2);for(int i=0;i<bar.getMenuCount();i++){if(bar.getMenu(i)!=null && bar.getMenu(i).getText().equals(app.language.base.getString("menu.tools")))index=i+1;}bar.add(menu,index);McpAccess.install(app);
        app.frmMain.setTitle("Amua (ReyJay) V 3.2.4 - Engine 0.3.6");
        javax.swing.Timer paneSetup=new javax.swing.Timer(300,e->{setupPanes(original,"main");split.setDividerLocation(Math.max(280,Math.min(480,preferences.getInt("sidebar_width",340))));split.addPropertyChangeListener(JSplitPane.DIVIDER_LOCATION_PROPERTY,event->{int width=split.getDividerLocation();if(width>=280&&width<=480)preferences.putInt("sidebar_width",width);});});paneSetup.setRepeats(false);paneSetup.start();
        long initialEpoch=epoch.get();SwingUtilities.invokeLater(()->{if(epoch.get()==initialEpoch&&!activityTimer.isRunning()){Map<String,Object> request=req("status");request.put("quiet",true);invoke("provider",request);}});
    }
    static void compactControlFonts(Container root){for(Component child:root.getComponents()){if(child instanceof AbstractButton)child.setFont(child.getFont().deriveFont(11f));if(child instanceof Container)compactControlFonts((Container)child);}}
    String text(String key){return java.util.ResourceBundle.getBundle("v21.WorkflowText",app.language.locale).getString(key);}
    JButton button(JPanel p,String title,Runnable action){JButton b=new JButton(title);b.addActionListener(e->{try{action.run();}catch(Exception x){append("Action unavailable: "+x.getMessage());}});p.add(b);return b;}
    void append(String s){conversation.append("\n"+s+"\n");conversation.setCaretPosition(conversation.getDocument().getLength());}
    void setupPanes(Container root,String key){int childIndex=0;for(Component component:root.getComponents()){String id=key+"_"+(childIndex++);if(component instanceof JSplitPane){JSplitPane pane=(JSplitPane)component;pane.setOneTouchExpandable(true);Component bottom=pane.getBottomComponent();boolean canvasBottom=bottom instanceof JTabbedPane&&bottom!=app.tabbedPaneBottom;double initial=pane.getOrientation()==JSplitPane.HORIZONTAL_SPLIT?0.8:canvasBottom?0.07:0.84;if(pane.getOrientation()==JSplitPane.VERTICAL_SPLIT&&!canvasBottom)consolePane=pane;pane.setResizeWeight(initial);if(pane.getLeftComponent()!=null)pane.getLeftComponent().setMinimumSize(new Dimension(0,0));if(pane.getRightComponent()!=null)pane.getRightComponent().setMinimumSize(new Dimension(0,0));pane.setDividerLocation(preferences.getDouble(id,initial));pane.addPropertyChangeListener(JSplitPane.DIVIDER_LOCATION_PROPERTY,event->{int length=pane.getOrientation()==JSplitPane.HORIZONTAL_SPLIT?pane.getWidth():pane.getHeight();if(length>0)preferences.putDouble(id,Math.max(0,Math.min(1,pane.getDividerLocation()/(double)length)));});}if(component instanceof Container)setupPanes((Container)component,id);}}
    void fit(){base.AmuaModel m=model();if(m==null)return;JComponent panel=m.type==0?m.panelTree:m.panelMarkov;JViewport viewport=(JViewport)SwingUtilities.getAncestorOfClass(JViewport.class,panel);if(viewport==null)return;Dimension content=panel.getPreferredSize(),view=viewport.getExtentSize();double factor=Math.min(view.width/(double)Math.max(1,content.width),view.height/(double)Math.max(1,content.height));int scale=Math.max(20,Math.min(200,(int)Math.floor(m.scale*factor)));m.rescale(scale);app.setZoomVal(scale);viewport.setViewPosition(new Point(0,0));}
    void select(){pendingChat=null;outlineCreated=false;outlineTarget=null;outlineTargetHash=null;lastProposalFailure=null;if(applyProposal!=null)applyProposal.setEnabled(false);JFileChooser f=new JFileChooser();f.setMultiSelectionEnabled(true);f.setFileSelectionMode(JFileChooser.FILES_AND_DIRECTORIES);if(f.showOpenDialog(this)==JFileChooser.APPROVE_OPTION){stop();history.clear();lastRequest=null;lastHelper=null;for(File x:f.getSelectedFiles())if(!paths.contains(x.getAbsolutePath()))paths.add(x.getAbsolutePath());sources.setText(String.join("\n",paths));project=null;selectionPlan=null;if(attachments!=null)attachments.reset();}}
    void clearSourceAttachments(){
        includeEmbeddedEvidence.setSelected(false);stop();pendingChat=null;lastProposalFailure=null;applyProposal.setEnabled(false);paths.clear();history.clear();lastRequest=null;lastHelper=null;sources.setText("");project=null;selectionPlan=null;if(attachments!=null)attachments.reset();
        status.setText("Attachments cleared");append("Source attachments cleared. Pasted images remain in local app support storage; nothing was sent.");
    }
    Map<String,Object> req(String action){Map<String,Object> r=new LinkedHashMap<>();r.put("action",action);return r;}
    static boolean isWindows(){return System.getProperty("os.name","").toLowerCase(java.util.Locale.ROOT).startsWith("windows");}
    static String pythonExecutable(String resources){return resources+(isWindows()?"/python/python.exe":"/python/bin/python3");}
    static String javaExecutable(String resources){return resources+"/runtime/bin/java"+(isWindows()?".exe":"");}
    static File nullDevice(){return new File(isWindows()?"NUL":"/dev/null");}
    void connectAccount(String mode,String account){stop();history.clear();lastRequest=null;lastHelper=null;Map<String,Object> r=req("connect");r.put("mode",mode);if(account!=null)r.put("account",account);invoke("provider",r);}
    static String accountDisplay(Map profile){String label=String.valueOf(profile.get("label")==null?"ChatGPT connection":profile.get("label"));Object email=profile.get("email")==null?profile.get("account"):profile.get("email");return email instanceof String&&!((String)email).isEmpty()?label+" · "+email:label;}
    void chooseAccount(Map<String,Object> data){
        Object items=data.get("accounts");List<Map> saved=new ArrayList<>();if(items instanceof List)for(Object item:(List)items)if(item instanceof Map)saved.add((Map)item);
        Object pendingData=data.get("pending_attempts");List<Map> pending=new ArrayList<>();if(pendingData instanceof List)for(Object item:(List)pendingData)if(item instanceof Map)pending.add((Map)item);
        if(saved.isEmpty()&&pending.isEmpty()&&!Boolean.TRUE.equals(data.get("removed"))){connectAccount("add",null);return;}
        JDialog dialog=new JDialog(app.frmMain,"ChatGPT accounts and workspaces",false);dialog.setLayout(new BorderLayout(6,6));
        JTextArea explanation=new JTextArea("Each saved connection belongs to the account and workspace selected when it was created. To use another account or workspace, add a new connection. OpenAI plan and workspace policies still apply.");explanation.setEditable(false);explanation.setLineWrap(true);explanation.setWrapStyleWord(true);explanation.setRows(4);dialog.add(explanation,BorderLayout.NORTH);
        DefaultListModel<String> labels=new DefaultListModel<>();int selected=0;for(int i=0;i<saved.size();i++){Map profile=saved.get(i);labels.addElement(accountDisplay(profile)+(Boolean.TRUE.equals(profile.get("active"))?" · active":"")+(!Boolean.TRUE.equals(profile.get("signed_in"))?" · signed out":""));if(Boolean.TRUE.equals(profile.get("active")))selected=i;}
        JList<String> list=new JList<>(labels);list.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);if(!saved.isEmpty())list.setSelectedIndex(selected);dialog.add(new JScrollPane(list),BorderLayout.CENTER);
        JPanel actions=new JPanel(new java.awt.GridLayout(0,1,4,4));
        JButton use=new JButton("Use selected connection");use.setEnabled(!saved.isEmpty());use.addActionListener(e->{int index=list.getSelectedIndex();if(index<0)return;Map profile=saved.get(index);dialog.dispose();stop();history.clear();lastRequest=null;if(Boolean.TRUE.equals(profile.get("signed_in"))){Map<String,Object> request=req("switch");request.put("account",profile.get("registration"));invoke("provider",request);}else connectAccount("reauthorize",String.valueOf(profile.get("registration")));});actions.add(use);
        JButton signIn=new JButton("Sign in again to selected connection");signIn.setEnabled(!saved.isEmpty());signIn.addActionListener(e->{int index=list.getSelectedIndex();if(index>=0){dialog.dispose();connectAccount("reauthorize",String.valueOf(saved.get(index).get("registration")));}});actions.add(signIn);
        JButton remove=new JButton("Remove selected connection");remove.setEnabled(!saved.isEmpty());remove.addActionListener(e->{int index=list.getSelectedIndex();if(index<0)return;Map profile=saved.get(index);if(!confirmConnectionRemoval(dialog,accountDisplay(profile)))return;Map<String,Object> request=req("remove");request.put("account",profile.get("registration"));dialog.dispose();stop();history.clear();lastRequest=null;lastHelper=null;invoke("provider",request);});actions.add(remove);
        button(actions,"Add another account or workspace",()->{dialog.dispose();connectAccount("add",null);});
        if(!pending.isEmpty())button(actions,"Retry an unfinished sign-in",()->{String[] attempts=new String[pending.size()];for(int i=0;i<attempts.length;i++)attempts[i]=String.valueOf(pending.get(i).get("label"));Object choice=JOptionPane.showInputDialog(dialog,"Retry only with the same account/workspace used for that attempt. Choose Add another account or workspace for a different one.","Unfinished sign-in",JOptionPane.QUESTION_MESSAGE,null,attempts,attempts[0]);if(choice==null)return;for(int i=0;i<attempts.length;i++)if(attempts[i].equals(choice)){Map<String,Object> request=req("connect");request.put("mode","retry");request.put("attempt_id",pending.get(i).get("attempt_id"));dialog.dispose();stop();history.clear();invoke("provider",request);break;}});
        if(!pending.isEmpty())button(actions,"Remove an unfinished sign-in",()->{String[] attempts=new String[pending.size()];for(int i=0;i<attempts.length;i++)attempts[i]=String.valueOf(pending.get(i).get("label"));Object choice=JOptionPane.showInputDialog(dialog,"Choose the unfinished sign-in to remove.","Unfinished sign-in",JOptionPane.QUESTION_MESSAGE,null,attempts,attempts[0]);if(choice==null)return;for(int i=0;i<attempts.length;i++)if(attempts[i].equals(choice)){if(!confirmConnectionRemoval(dialog,attempts[i]))return;Map<String,Object> request=req("remove");request.put("attempt_id",pending.get(i).get("attempt_id"));dialog.dispose();stop();history.clear();lastRequest=null;lastHelper=null;invoke("provider",request);break;}});
        button(actions,"Close",dialog::dispose);dialog.add(actions,BorderLayout.SOUTH);dialog.setSize(560,600);dialog.setLocationRelativeTo(app.frmMain);dialog.setVisible(true);
    }
    boolean confirmConnectionRemoval(Component parent,String label){return JOptionPane.showConfirmDialog(parent,"Remove "+label+" from Amua?\nIts saved sign-in will be cleared. You can add it again later.","Remove connection",JOptionPane.OK_CANCEL_OPTION,JOptionPane.QUESTION_MESSAGE)==JOptionPane.OK_OPTION;}
    void provider(String action){
        if("status".equals(action)&&activityTimer.isRunning()&&"chat-request".equals(activeAction)){
            append("The AI request is still active. "+status.getText()+". "+activity.getString()+". Use Stop to cancel it.");return;
        }
        invoke("provider",req(action));
    }
    void workflow(String action){Map<String,Object> r=req(action);if(action.equals("preview-synthetic")){if(project==null)return;r.put("project",project);}else if(action.equals("intake")){if(paths.isEmpty()){append("Select files first.");return;}if(hasSelectedFolder()){beginFolderRead(null);return;}r.put("paths",new ArrayList<>(paths));}else if(action.equals("save")||action.equals("open")){if(action.equals("save") && project==null){append("Inspect sources first.");return;}JFileChooser f=new JFileChooser();f.setSelectedFile(new File("draft.amuax"));if((action.equals("save")?f.showSaveDialog(this):f.showOpenDialog(this))!=JFileChooser.APPROVE_OPTION)return;File target=f.getSelectedFile();if(action.equals("save") && target.exists() && JOptionPane.showConfirmDialog(this,"Replace this project?","Save",JOptionPane.YES_NO_OPTION)!=JOptionPane.YES_OPTION)return;r.put("path",target.getAbsolutePath());if(action.equals("save")&&target.exists()){try{if(target.length()>64*1024*1024)throw new IOException("Project too large for this save path");byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(target.toPath()));StringBuilder h=new StringBuilder();for(byte b:hash)h.append(String.format("%02x",b&255));r.put("expected_hash",h.toString());}catch(Exception e){append("Cannot verify destination; save a copy.");return;}}if(project!=null)r.put("project",project);}invoke("workflow",r);}
    boolean hasSelectedFolder(){for(String path:paths)if(new File(path).isDirectory())return true;return false;}
    int pendingSources(){if(selectionPlan==null)return 0;int count=0;for(Object o:(List)selectionPlan.get("entries"))if("pending".equals(((Map)o).get("status")))count++;return count;}
    String folderStatus(){if(selectionPlan==null)return "No folder snapshot.";StringBuilder report=new StringBuilder();for(Object item:(List)selectionPlan.get("entries")){Map entry=(Map)item;report.append(entry.get("display_path")).append(" — ").append(entry.get("status"));if(entry.get("reason")!=null)report.append(": ").append(entry.get("reason"));report.append("\n");}return report.toString();}
    void beginFolderRead(String question){project=null;selectionPlan=null;history.clear();Map<String,Object> r=req("selection-plan");r.put("paths",new ArrayList<>(paths));Map<String,Object> options=new LinkedHashMap<>();options.put("recursive",includeSubfolders.isSelected());r.put("options",options);if(question!=null)r.put("question",question);invoke("workflow",r);}
    void readFolderBatch(int offset,String question){Map<String,Object> r=req("intake-batch");r.put("selection",selectionPlan);r.put("offset",offset);r.put("count",20);if(project!=null)r.put("project",project);if(question!=null)r.put("question",question);invoke("workflow",r);}
    void send(){
        if(attachments!=null&&attachments.pending>0){append("Wait for the pasted image to finish preparing before sending.");return;}
        String question=message.getText().trim();
        if(question.isEmpty()){status.setText("Enter a question first");return;}
        if(selectionPlan!=null&&pendingSources()>0){append("Folder inspection is incomplete. Read the remaining batches before sending their content.");return;}
        if(project==null&&!paths.isEmpty()){
            if(hasSelectedFolder()){beginFolderRead(question);return;}
            Map<String,Object> intake=req("intake");
            intake.put("paths",new ArrayList<>(paths));
            intake.put("continue_send",true);
            intake.put("question",question);
            append("Inspecting selected files locally before preparing your request…");
            invoke("workflow",intake);
            return;
        }
        reviewOutgoing(question);
    }
    Map<String,Object> chatRequest(String text){
        Map<String,Object> r=req("chat-preview");r.put("budget_session_id",budgetSession);r.put("idle_timeout_seconds",modelStallTimeout());r.put("text",text);r.put("history",new ArrayList<>(history));r.put("paths",new ArrayList<>(paths));
        r.put("include_embedded_evidence",includeEmbeddedEvidence.isSelected());
        if(selectionPlan!=null){List<String> sourcePaths=new ArrayList<>();for(Object entry:(List)selectionPlan.get("entries")){Map e=(Map)entry;if(e.get("source_id")!=null)sourcePaths.add(String.valueOf(e.get("path")));}r.put("source_paths",sourcePaths);}
        if(project!=null)r.put("project",project);
        base.AmuaModel current=includeWorkspace.isSelected()?model():null;Map<String,Object> snapshot=WorkspaceSnapshot.capture(current);
        if(current==outlineTarget&&snapshot!=null&&Objects.equals(snapshot.get("sha256"),outlineTargetHash)){current=null;snapshot=null;}
        if(snapshot!=null)r.put("workspace",snapshot);
        chatTarget=current;chatTargetHash=snapshot==null?null:String.valueOf(snapshot.get("sha256"));
        r.put("make_outline",!outlineCreated&&text.toLowerCase(java.util.Locale.ROOT).matches("(?s).*(create|build|generate|make|draw).*"));
        return r;
    }
    void reviewOutgoing(String text){
        pendingChat=null;applyProposal.setEnabled(false);Map<String,Object> r=chatRequest(text);append("You: "+text);invoke("provider",r);
    }
    void acceptPreliminaryOutline(Map<String,Object> result)throws Exception{
        if(!(result.get("draft_xml") instanceof String))return;
        ModelChat.apply(app,(String)result.get("draft_xml"),null,null,false);outlineCreated=true;
        outlineTarget=model();outlineTargetHash=(String)WorkspaceSnapshot.capture(outlineTarget).get("sha256");
        append("Amua: "+result.get("draft_text"));status.setText("Preliminary outline · final image model is not applied");
    }
    void reviewChat(Map<String,Object> result,Map<String,Object> request)throws Exception{
        acceptPreliminaryOutline(result);
        Map<String,Object> next=new LinkedHashMap<>(request);next.put("action","chat-request");next.put("approved_context_hash",result.get("context_hash"));next.put("approved_max_calls",result.get("required_calls"));
        next.put("approved_recipient",result.get("recipient"));next.put("approved_model",result.get("resolved_model"));
        int calls=boundedCount(result.get("required_calls"));
        if(calls>0){
            if(Boolean.FALSE.equals(result.get("can_send"))){append("Request unavailable: connect an eligible account and narrow evidence to 450,000 bytes. No inference was sent.");return;}
            JTextArea info=new JTextArea("Recipient: "+json(result.get("recipient"))+"\nModel: "+result.get("resolved_model")+"\n\nOutgoing inventory: "+json(result.get("outgoing_manifest"))+"\n\nComplete outgoing text (selected images are listed above):\n"+result.get("outgoing_text")+"\n\nOne request; no automatic retry. Idle timeout: "+request.get("idle_timeout_seconds")+" seconds.",20,65);info.setLineWrap(true);info.setWrapStyleWord(true);info.setEditable(false);info.setCaretPosition(0);
            if(JOptionPane.showConfirmDialog(this,new JScrollPane(info),"Review ChatGPT request",JOptionPane.OK_CANCEL_OPTION)!=JOptionPane.OK_OPTION){status.setText("Request cancelled · editable draft retained");return;}
        }
        invoke("provider",next);
    }
    void receiveChat(Map<String,Object> result,Map<String,Object> request){
        append("ChatGPT: "+result.get("text"));
        Map proposal=result.get("proposal") instanceof Map?(Map)result.get("proposal"):null;
        if(proposal!=null){
            String intent=String.valueOf(proposal.get("intent"));
            if(result.get("candidate_xml") instanceof String){
                if(Boolean.TRUE.equals(result.get("local_answer"))){try{ModelChat.apply(app,(String)result.get("candidate_xml"),chatTarget,chatTargetHash,true);pendingChat=null;applyProposal.setEnabled(false);append("Your answer was applied as an undoable native-model edit.");}catch(Exception error){append("Answer not applied: "+error.getMessage());}return;}
                pendingChat=result;pendingChatRequest=request;pendingTarget=chatTarget;pendingTargetHash=chatTargetHash;lastProposalFailure=null;applyProposal.setEnabled(true);
                if(pendingTarget==null&&outlineIsUnchanged()){pendingTarget=outlineTarget;pendingTargetHash=outlineTargetHash;}
                append("The FINAL editable tree proposal is ready. Choose Apply tree proposal to review and apply it; the preliminary outline is not the result.");}
            else if(intent.equals("run")||intent.equals("validate")||intent.equals("sensitivity")){
                Map expected=request.get("workspace") instanceof Map?(Map)request.get("workspace"):null;Map current=WorkspaceSnapshot.capture(model());
                if(expected==null||current==null||!Objects.equals(expected.get("sha256"),current.get("sha256")))append("The inspected model changed. Send the analysis request again for the current model.");
                else if(Boolean.TRUE.equals(result.get("local_command")))analyseChat(intent,proposal.get("analysis") instanceof Map?(Map)proposal.get("analysis"):null);
                else append("ChatGPT suggested an analysis. Use the Validate, Run or Sensitivity button to authorize that action; the suggestion was not executed.");
            }
        }
        Map<String,Object> user=new LinkedHashMap<>();user.put("role","user");user.put("content",request.get("text"));Map<String,Object> assistant=new LinkedHashMap<>();assistant.put("role","assistant");assistant.put("content",result.get("text"));history.add(user);history.add(assistant);
        while(!history.isEmpty()&&(history.size()>10||json(history).getBytes(StandardCharsets.UTF_8).length>60000))history.remove(0);
    }
    void applyChatProposal(){
        if(pendingChat==null){append("No unapplied proposal. Describe the tree or changes in chat and press Send.");return;}
        try{
            Map proposal=(Map)pendingChat.get("proposal"),candidate=(Map)proposal.get("model");List nodes=(List)candidate.get("nodes");List questions=(List)proposal.get("questions");
            JTextArea detail=new JTextArea(String.valueOf(proposal.get("message"))+"\n\n"+nodes.size()+" nodes; "+questions.size()+" unresolved questions.\nExpressions containing UNRESOLVED are intentional and cannot be calculated.\n\n"+json(candidate),20,65);detail.setEditable(false);detail.setLineWrap(true);detail.setWrapStyleWord(true);
            boolean outlineReplacement=pendingTarget==outlineTarget&&outlineIsUnchanged();
            Object[] options=outlineReplacement?new Object[]{"Create new tab","Replace preliminary outline","Cancel"}:pendingTarget!=null&&"edit".equals(proposal.get("intent"))?new Object[]{"Create new tab","Apply undoable edit","Cancel"}:new Object[]{"Create new tab","Cancel"};
            int choice=JOptionPane.showOptionDialog(this,new JScrollPane(detail),"Review editable tree proposal",JOptionPane.DEFAULT_OPTION,JOptionPane.QUESTION_MESSAGE,null,options,options[0]);
            if(choice<0||choice==options.length-1)return;
            applyPendingChat(choice==1&&options.length==3);
        }catch(Exception error){append("Proposal not applied: "+error.getMessage());}
    }
    boolean outlineIsUnchanged(){
        return outlineTarget!=null&&Objects.equals(WorkspaceSnapshot.capture(outlineTarget).get("sha256"),outlineTargetHash);
    }
    void applyPendingChat(boolean replace)throws Exception{
        if(pendingChat==null)throw new IllegalStateException("No pending proposal");
        ModelChat.apply(app,(String)pendingChat.get("candidate_xml"),pendingTarget,pendingTargetHash,replace);
        append("Applied FINAL editable native tree. Use Questions and Review inputs for remaining reviews; save a new .amua file. Original-engine validation is required before calculations.");
        pendingChat=null;outlineTarget=null;outlineTargetHash=null;applyProposal.setEnabled(false);fit();status.setText("Final tree applied · review inputs and validate");
    }
    void recordProposalFailure(Object error,Map<String,Object> request){
        String reason=error instanceof Map?String.valueOf(((Map)error).get("category")):String.valueOf(error);
        lastProposalFailure=(reason.startsWith("invalid_")||reason.contains("unsupported")||reason.startsWith("cyclic_")||reason.startsWith("disconnected_")||reason.startsWith("native_")||reason.startsWith("reserved_"))?reason:null;pendingChat=null;applyProposal.setEnabled(false);
        append("FINAL TREE NOT APPLIED. Any preliminary source outline remains incomplete. Reason: "+reason+". Retry will carry this validation reason and ask for fresh approval.");
    }
    void saveChatModel(){
        base.AmuaModel current=model();if(current==null){append("Create or open a model first.");return;}
        JFileChooser chooser=new JFileChooser();chooser.setSelectedFile(new File((current.name==null?"Untitled":current.name)+".amua"));
        if(chooser.showSaveDialog(this)!=JFileChooser.APPROVE_OPTION)return;
        Path path=chooser.getSelectedFile().toPath();if(!path.toString().toLowerCase(java.util.Locale.ROOT).endsWith(".amua"))path=Paths.get(path+".amua");
        try{base.AtomicModelSave.save(current,path,false);current.filepath=path.toAbsolutePath().toString();base.AtomicModelSave.remember(current,path);current.unsavedChanges=false;String filename=path.getFileName().toString();current.name=filename.substring(0,filename.length()-5);app.setTabName(current.name,current.type);app.frmMain.setTitle(app.workflowTitle(current));append("Saved new native model with its AI questions/source evidence: "+path.toAbsolutePath());}
        catch(Exception error){append("Model not saved: "+error.getMessage()+". Choose a new path; the open model is preserved.");}
    }
    void showChatQuestions(){
        Map state=ModelChat.state(model());Map proposal=state==null?null:(Map)state.get("proposal");
        if(proposal==null&&pendingChat!=null)proposal=(Map)pendingChat.get("proposal");
        if(proposal==null){append("No saved AI questions for this model. Ask chat to review it.");return;}
        List questions=(List)proposal.get("questions");StringBuilder text=new StringBuilder();for(Object item:questions){Map q=(Map)item;text.append(q.get("id")).append(": ").append(q.get("text")).append("\n\n");}
        JTextArea view=new JTextArea(text.length()==0?"No unresolved AI questions. Validate before running.":text.toString(),20,60);view.setEditable(false);view.setLineWrap(true);view.setWrapStyleWord(true);
        JOptionPane.showMessageDialog(this,new JScrollPane(view),"Model questions · answer in chat",JOptionPane.INFORMATION_MESSAGE);
    }
    void reviewProposedInputs(){
        Map state=ModelChat.state(model());Map proposal=pendingChat!=null?(Map)pendingChat.get("proposal"):state==null?null:(Map)state.get("proposal");
        Object issues=proposal==null?null:proposal.get("input_review");
        if(!(issues instanceof List)||((List)issues).isEmpty()){append("No pending scientific input review for this model.");return;}
        JTextArea view=new JTextArea("Check every expression, cited source value, unit and transformation below. Confirm only inputs you can support. Structure approval is separate.\n\n"+json(issues),22,65);view.setEditable(false);view.setLineWrap(true);view.setWrapStyleWord(true);view.setCaretPosition(0);
        if(pendingChat!=null){JOptionPane.showMessageDialog(this,new JScrollPane(view),"Proposed inputs · apply the proposal before confirming",JOptionPane.INFORMATION_MESSAGE);return;}
        Object[] options={"Close","Confirm these inputs"};int choice=JOptionPane.showOptionDialog(this,new JScrollPane(view),"Review scientific inputs",JOptionPane.DEFAULT_OPTION,JOptionPane.QUESTION_MESSAGE,null,options,options[0]);
        if(choice==1){message.setText("approve inputs");send();}
    }
    void saveShareableCopy(){
        base.AmuaModel current=model();if(current==null){append("Open a model first.");return;}
        JFileChooser chooser=new JFileChooser();chooser.setSelectedFile(new File((current.name==null?"Untitled":current.name)+"-without-source-inventory.amua"));
        if(chooser.showSaveDialog(this)!=JFileChooser.APPROVE_OPTION)return;
        Path path=chooser.getSelectedFile().toPath();if(!path.toString().toLowerCase(java.util.Locale.ROOT).endsWith(".amua"))path=Paths.get(path+".amua");
        try{base.AmuaModel copy=ModelChat.withoutSourceInventory(current);base.AtomicModelSave.save(copy,path,false);append("Saved copy without embedded source inventory: "+path+". Model inputs, notes, source labels and review restrictions remain; review them before sharing.");}
        catch(Exception error){append("Copy not saved: "+error.getMessage());}
    }
    void readPdfPages(){
        if(project==null){append("Inspect the PDF locally first.");return;}
        JFileChooser chooser=new JFileChooser();if(chooser.showOpenDialog(this)!=JFileChooser.APPROVE_OPTION)return;
        String input=JOptionPane.showInputDialog(this,"First page, number of pages (1–20), for example 21, 20. Each batch has a 60-second OCR budget; unreadable pages stay unresolved.","Read PDF page batch",JOptionPane.QUESTION_MESSAGE);
        if(input==null)return;try{String[] values=input.split(",");Map<String,Object> request=req("ocr-batch");request.put("project",project);request.put("path",chooser.getSelectedFile().getAbsolutePath());request.put("start_page",Integer.valueOf(values[0].trim()));request.put("page_count",Integer.valueOf(values[1].trim()));invoke("workflow",request);}catch(Exception error){append("Enter a positive first page and 1–20 pages.");}
    }
    void sensitivityChat(){
        String value=JOptionPane.showInputDialog(this,"Enter parameter, minimum, maximum, points (e.g. p, 0.1, 0.3, 11). Use source-supported bounds.","One-way sensitivity",JOptionPane.QUESTION_MESSAGE);
        if(value==null)return;try{String[] parts=value.split(",");Map<String,Object> a=new LinkedHashMap<>();a.put("parameter",parts[0].trim());a.put("minimum",Double.valueOf(parts[1].trim()));a.put("maximum",Double.valueOf(parts[2].trim()));a.put("points",Integer.valueOf(parts[3].trim()));analyseChat("sensitivity",a);}catch(Exception error){append("Enter a parameter and valid numeric bounds/points.");}
    }
    void analyseChat(String action,Map analysis){
        base.AmuaModel current=model();if(current==null){append("Open or create a model first.");return;}
        try{
            append("Original-engine validation of "+(current.name==null?"Untitled":current.name)+"…");
            if(!current.checkModel(app.workflowConsole(),true)){append("Validation failed. See the original engine console. The tree remains editable; answer the missing inputs before calculating.");return;}
            if(action.equals("validate")){append("Original-engine validation passed. No calculation was run.");return;}
            Map<String,Object> snapshot=WorkspaceSnapshot.capture(current);Map<String,Object> r=req("engine-analysis");r.put("xml",snapshot.get("xml"));r.put("target_hash",snapshot.get("sha256"));r.put("operation",action);if(analysis!=null)r.put("analysis",analysis);invoke("engine",r);
        }catch(Exception error){append("Analysis unavailable: "+error.getMessage());}
    }
    Map<String,Object> retryRequest(){
        if(lastRequest==null)return null;
        Map<String,Object> next=new LinkedHashMap<>(lastRequest);
        if("provider".equals(lastHelper)&&("request".equals(next.get("action"))||"chat-request".equals(next.get("action")))){next.put("action","chat-request".equals(next.get("action"))?"chat-preview":"preview");next.remove("approved_max_calls");next.remove("approved_transport_hash");next.remove("approved_review_hash");}
        if("chat-preview".equals(next.get("action"))){next.put("make_outline",false);next.put("idle_timeout_seconds",modelStallTimeout());next.remove("approved_context_hash");}
        if("chat-preview".equals(next.get("action"))&&lastProposalFailure!=null){
            List<Map<String,Object>> repairHistory=new ArrayList<>();
            if(next.get("history") instanceof List)repairHistory.addAll((List)next.get("history"));
            while(repairHistory.size()>10)repairHistory.remove(0);
            Map<String,Object> issue=new LinkedHashMap<>();issue.put("role","assistant");issue.put("content","The local Amua validator rejected my previous proposal: "+lastProposalFailure+". Return a corrected complete model from the selected sources. Retain unknowns as non-executable structure questions; do not guess targets or weaken validation.");repairHistory.add(issue);
            next.put("history",repairHistory);
        }
        return next;
    }
    void retryLast(){Map<String,Object> next=retryRequest();if(next!=null)invoke(lastHelper,next);}
    int modelStallTimeout(){int value=preferences.getInt("model_chat_idle_seconds",180);return value>=60&&value<=1800?value:180;}
    void chooseModelStallTimeout(){
        String[] options={"2 minutes","3 minutes","5 minutes","10 minutes"};int[] seconds={120,180,300,600};int selected=1;for(int i=0;i<seconds.length;i++)if(seconds[i]==modelStallTimeout())selected=i;
        Object choice=JOptionPane.showInputDialog(this,"Stop only after this long without meaningful ChatGPT progress. A response can run longer while data continues arriving. Stop remains available. Applies to the next Send/Retry.","AI stall timeout",JOptionPane.QUESTION_MESSAGE,null,options,options[selected]);
        if(choice==null)return;for(int i=0;i<options.length;i++)if(options[i].equals(choice)){preferences.putInt("model_chat_idle_seconds",seconds[i]);append("AI stall timeout: "+options[i]+" without meaningful progress. There is no fixed total-duration cutoff while the response progresses.");}
    }
    void acceptModelProgress(Map reply,long token){
        synchronized(processLock){
        if(token!=epoch.get()||!"chat-request".equals(activeAction)||!"model_progress".equals(reply.get("event"))||!Boolean.TRUE.equals(reply.get("meaningful")))return;
        Object sequence=reply.get("progress_sequence");if(!(sequence instanceof Number))return;double value=((Number)sequence).doubleValue();
        if(!Double.isFinite(value)||value!=Math.rint(value)||value<=lastModelProgressSequence||value>Long.MAX_VALUE)return;
        lastModelProgressSequence=(long)value;lastModelProgressNanos=System.nanoTime();
        }
    }
    void updateActivity(){
        long seconds=Math.max(0,(System.nanoTime()-activityStarted)/1000000000L);
        if("chat-request".equals(activeAction)){
            long idle=Math.max(0,(System.nanoTime()-lastModelProgressNanos)/1000000000L);
            activity.setString("Working · "+seconds+"s · last progress "+idle+"s ago");
            if(idle>=activeModelIdleSeconds){stop();append("No meaningful ChatGPT response progress for "+activeModelIdleSeconds+"seconds. The request was stopped and your editable tree is preserved. Retry starts a fresh request; no automatic retry was started. You can adjust AI Workflow → AI stall timeout.");}
        }else{
            activity.setString("Working · "+seconds+"s");
            if(seconds>=110&&"engine-analysis".equals(activeAction)){stop();append("This engine analysis reached its110-second deadline and was stopped. The editable tree is preserved. No automatic retry was started.");}
        }
    }
    void finishActivity(){activityTimer.stop();activity.setIndeterminate(false);activity.setVisible(false);}
    void beginActivity(String helper,Map<String,Object> request){String action=String.valueOf(request.get("action"));String label;
        if("workflow".equals(helper))label="Reading / preparing local sources…";
        else if("connect".equals(action))label="Connecting to ChatGPT · complete sign-in in your browser…";
        else if("request".equals(action)||"chat-request".equals(action))label="Waiting for ChatGPT · Stop remains available…";
        else if("accounts".equals(action)||"status".equals(action))label="Checking ChatGPT connection…";
        else if("remove".equals(action)||"logout".equals(action))label="Updating ChatGPT connections…";
        else label="Preparing ChatGPT request…";
        status.setText(label);activityStarted=System.nanoTime();lastModelProgressNanos=activityStarted;lastModelProgressSequence=0;
        activeModelIdleSeconds=modelStallTimeout();Object idleSetting=request.get("idle_timeout_seconds");if(idleSetting instanceof Number){int value=((Number)idleSetting).intValue();if(value>=60&&value<=1800)activeModelIdleSeconds=value;}
        updateActivity();activity.setVisible(true);activity.setIndeterminate(true);activityTimer.start();}
    void stop(){finishActivity();Process p;synchronized(processLock){epoch.incrementAndGet();p=process;process=null;}if(p!=null){p.destroy();new Thread(()->{try{if(!p.waitFor(2500,java.util.concurrent.TimeUnit.MILLISECONDS))p.destroyForcibly();}catch(InterruptedException e){Thread.currentThread().interrupt();}},"Amua helper cleanup").start();}status.setText("Stopped · late replies discarded");}
    void invoke(String helper,Map<String,Object> request){
        if(activityTimer.isRunning()&&"connect".equals(activeAction)&&!"connect".equals(request.get("action"))){append("Sign-in is still running. Finish in the browser, or choose Stop before starting another operation.");return;}
        stop();long token=epoch.get();lastRequest=request;lastHelper=helper;activeAction=String.valueOf(request.get("action"));beginActivity(helper,request);new SwingWorker<Map<String,Object>,String>(){
        protected Map<String,Object> doInBackground() throws Exception {
            String resources=System.getProperty("amua.resources");String python=pythonExecutable(resources);
            if(!Files.isExecutable(Paths.get(python)))throw new IOException("Bundled Python runtime missing");
            ProcessBuilder b=new ProcessBuilder(python,"-B",resources+"/"+helper+"_helper.py");b.environment().put("PYTHONPATH",resources+"/pythonlib");b.redirectError(ProcessBuilder.Redirect.to(nullDevice()));Process p=b.start();synchronized(processLock){if(token!=epoch.get()){p.destroyForcibly();throw new InterruptedException("Operation cancelled before helper input");}process=p;}
            Map<String,Object> wire=new LinkedHashMap<>(request);if(helper.equals("provider")&&("request".equals(request.get("action"))||"chat-request".equals(request.get("action"))||"connect".equals(request.get("action"))))wire.put("progress_events",true);
            try(OutputStream out=p.getOutputStream()){out.write(json(wire).getBytes(StandardCharsets.UTF_8));}
            ScriptEngine engine=new ScriptEngineManager().getEngineByName("nashorn");
            ByteArrayOutputStream line=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n,total=0;Map<String,Object> result=null;
            while((n=p.getInputStream().read(buffer))!=-1){
                total+=n;if(total>32*1024*1024){p.destroyForcibly();throw new IOException("Response too large");}
                for(int i=0;i<n;i++){
                    if(buffer[i]==10){if(line.size()>0){Map<String,Object> reply=parseReply(engine,line.toByteArray());line.reset();if(isProgress(reply)){acceptModelProgress(reply,token);publish(progressLabel(reply));}else result=reply;}}
                    else line.write(buffer[i]);
                }
            }
            if(line.size()>0){Map<String,Object> reply=parseReply(engine,line.toByteArray());if(!isProgress(reply))result=reply;else{acceptModelProgress(reply,token);publish(progressLabel(reply));}}
            if(p.waitFor()!=0)throw new IOException("Helper failed; no project changed");
            if(result==null)throw new IOException("No completed response was received");return result;
        }
        protected void process(List<String> updates){if(token==epoch.get()&&!updates.isEmpty())status.setText(updates.get(updates.size()-1));}

        protected void done(){if(token!=epoch.get())return;finishActivity();process=null;try{Map<String,Object> result=get();if(Boolean.TRUE.equals(result.get("chat_preview"))){reviewChat(result,request);return;}if(Boolean.TRUE.equals(result.get("ok"))&&"chat-request".equals(request.get("action"))){receiveChat(result,request);if(!activityTimer.isRunning())status.setText(pendingChat!=null?"Proposal ready · click Apply tree proposal":"Reply ready · answer questions");return;}if(Boolean.TRUE.equals(result.get("ok"))&&"engine-analysis".equals(request.get("action"))){append("Original engine: "+result.get("text"));app.workflowConsole().print("\nAI Workflow analysis on snapshot "+request.get("target_hash")+"\n"+result.get("text")+"\n");status.setText("Original-engine analysis completed");Map<String,Object> evidence=new LinkedHashMap<>();evidence.put("role","assistant");evidence.put("content","Original-engine results on snapshot "+request.get("target_hash")+": "+result.get("text"));history.add(evidence);return;}if(Boolean.FALSE.equals(result.get("ok"))){if("chat-request".equals(request.get("action")))recordProposalFailure(result.get("error"),request);append(friendlyError(result.get("error")));status.setText("connect".equals(request.get("action"))?"Sign-in failed · see details below":"Needs attention");
                    if("connect".equals(request.get("action"))&&result.get("error") instanceof Map){Map error=(Map)result.get("error");Object pending=error.get("pending_attempt_id");if(pending instanceof String){Object[] options={"Retry sign-in","Later"};if(JOptionPane.showOptionDialog(WorkflowPanel.this,friendlyError(error),"ChatGPT sign-in did not finish",JOptionPane.DEFAULT_OPTION,JOptionPane.WARNING_MESSAGE,null,options,options[0])==0){Map<String,Object> retry=req("connect");retry.put("mode","retry");retry.put("attempt_id",pending);invoke("provider",retry);}}}return;}
                if(result.get("selection") instanceof Map){
                    selectionPlan=(Map<String,Object>)result.get("selection");
                    if(result.get("project") instanceof Map)project=(Map<String,Object>)result.get("project");
                    if("selection-plan".equals(request.get("action"))){append("Folder snapshot: "+((List)selectionPlan.get("entries")).size()+" visible source files. Reading progressively…");if(pendingSources()>0){readFolderBatch(0,(String)request.get("question"));return;}}
                    else if(result.get("pending") instanceof Number&&((Number)result.get("pending")).intValue()>0){int total=((List)selectionPlan.get("entries")).size();append("Inspected "+(total-pendingSources())+" of "+total+" files. Continuing…");readFolderBatch(((Number)result.get("next_offset")).intValue(),(String)request.get("question"));return;}
                    if(project==null){append("No selected source could be extracted.\n"+folderStatus());status.setText("Needs attention");return;}append("Folder inspection finished. Unreadable and unsupported sources remain listed for review.");status.setText("Folder sources ready for review");if(request.get("question") instanceof String)reviewOutgoing((String)request.get("question"));return;
                }
                if(helper.equals("provider")&&result.get("accounts") instanceof List){if(Boolean.TRUE.equals(result.get("removed"))){if(result.get("message") instanceof String)append((String)result.get("message"));status.setText(Boolean.TRUE.equals(result.get("connected"))?"Using ChatGPT · "+accountDisplay(result):"AI disconnected · manual Amua available");if(Boolean.FALSE.equals(result.get("remote_revocation_confirmed")))JOptionPane.showMessageDialog(WorkflowPanel.this,String.valueOf(result.get("message")),"Connection removed locally",JOptionPane.INFORMATION_MESSAGE);}else status.setText("Choose a ChatGPT connection");chooseAccount(result);return;}
                if(helper.equals("provider")&&request.get("action").equals("preview")){
                    if(Boolean.FALSE.equals(result.get("connected"))){append("Choose Continue with ChatGPT and add or select your account before sending.");status.setText("Sign-in required");return;}
                    if(Boolean.FALSE.equals(result.get("plan_enabled"))){append("You are signed in, but this account or workspace has not enabled eligible ChatGPT plan usage. Choose another connection or enable access in ChatGPT settings. Manual Amua remains available.");status.setText("ChatGPT plan access unavailable");return;}
                    String info="Source chunks already reviewed: "+(result.get("completed_chunks")==null?0:result.get("completed_chunks"))+"\nConnection: "+result.get("account")+"\nUsage source: ChatGPT plan\nModel: "+result.get("model")+"\nThis request requires "+result.get("required_calls")+" remote calls ("+result.get("chunk_count")+" source chunks).\nCalls counted this session: "+result.get("calls_used")+". Amua has no session call cap.\nStop discards late output; it cannot guarantee immediate remote cancellation.\n\nSend the reviewed material?";
                    int needed=boundedCount(result.get("required_calls"));
                    if(Boolean.FALSE.equals(result.get("can_send"))||Boolean.FALSE.equals(result.get("feasible"))){
                        append("This request could not be prepared. Review the selected source scope before sending.");status.setText("Request needs review");return;
                    }
                    if(result.get("transport_format")!=null)info+="\nSource representation: "+result.get("transport_format")+" (all source records retained).";
                    if(JOptionPane.showConfirmDialog(WorkflowPanel.this,info,"Review AI request",JOptionPane.OK_CANCEL_OPTION)==JOptionPane.OK_OPTION){invoke("provider",approvedRequest(request,result));}else status.setText("Request cancelled before sending");return;
                }if(result.get("preview") instanceof Map){preview((Map<String,Object>)result.get("preview"));return;}if(result.get("project") instanceof Map){project=(Map<String,Object>)result.get("project");append("Project updated. Review its hierarchy, sources and unresolved questions.");if(result.get("summary") instanceof Map){Object unresolved=((Map)result.get("summary")).get("unreadable_or_failed_regions");if(unresolved instanceof Number&&((Number)unresolved).intValue()>0)append("Some source regions remain unresolved. Source inventory shows the failure reason. Use Read PDF pages for another explicit OCR batch, or provide a searchable copy.");}
                    if(Boolean.TRUE.equals(request.get("continue_send"))){
                        status.setText("Sources inspected · review outgoing material");
                        reviewOutgoing(String.valueOf(request.get("question")));
                        return;
                    }
                }else if(result.get("text") instanceof String){Object outgoingProject=request.get("project");if(outgoingProject instanceof Map&&((Map)outgoingProject).get("workspace_model") instanceof Map){Map previous=(Map)((Map)outgoingProject).get("workspace_model");Map current=WorkspaceSnapshot.capture(model());if(current==null||!Objects.equals(previous.get("sha256"),current.get("sha256")))append("These suggestions refer to an earlier workspace snapshot. The current model has changed.");}append("ChatGPT: "+result.get("text"));Map<String,Object> user=new LinkedHashMap<>();user.put("role","user");user.put("content",request.get("text"));Map<String,Object> assistant=new LinkedHashMap<>();assistant.put("role","assistant");assistant.put("content",result.get("text"));history.add(user);history.add(assistant);while(!history.isEmpty()&&(history.size()>10||json(history).getBytes(StandardCharsets.UTF_8).length>60000))history.remove(0);}else if(result.containsKey("connected")){
                    boolean connected=Boolean.TRUE.equals(result.get("connected"));
                    boolean planAvailable=!Boolean.FALSE.equals(result.get("plan_enabled"));
                    if(!Boolean.TRUE.equals(request.get("quiet")))append(connected?(planAvailable?"Connected to ChatGPT. Eligible requests use your ChatGPT plan. You can manage usage from Manage usage.":"Signed in to ChatGPT. This connection has no eligible plan access enabled; manual Amua remains available."):"ChatGPT is disconnected. Choose Continue with ChatGPT to connect.");
                    String label=accountDisplay(result);
                    status.setText(connected?(planAvailable?"Using ChatGPT plan · "+label:"Signed in · AI plan access unavailable"):"AI disconnected · manual Amua available");
                    if(connected&&planAvailable&&"connect".equals(request.get("action"))&&!preferences.getBoolean("chatgpt_plan_notice_shown",false)){JOptionPane.showMessageDialog(WorkflowPanel.this,"You're using your ChatGPT plan. Eligible AI requests use that account's plan allowance. Manage limits and access through Manage usage.","ChatGPT plan connected",JOptionPane.INFORMATION_MESSAGE);preferences.putBoolean("chatgpt_plan_notice_shown",true);}
                    return;
                }else append(json(result));if(result.containsKey("summary"))append(json(result.get("summary")));status.setText(helper.equals("provider")?"Connection operation finished — check response":"Local operation finished");}catch(Exception e){status.setText("Operation failed · manual Amua available");append("Operation failed: "+(e.getCause()!=null?e.getCause().getMessage():e.getMessage()));}}
    }.execute();}
    static boolean isProgress(Map reply){return "model_progress".equals(reply.get("event"))||"progress".equals(reply.get("event"))||"auth_progress".equals(reply.get("event"))||"browser_consent_required".equals(reply.get("event"));}
    static String progressLabel(Map reply){
        if("model_progress".equals(reply.get("event"))){
            String phase=String.valueOf(reply.get("phase"));
            if("thinking".equals(phase))return "ChatGPT is working · waiting for model text · "+reply.get("elapsed_seconds")+"s";
            if("finishing".equals(phase))return "Finishing model proposal · "+reply.get("characters")+" characters";
            return "Receiving model proposal · "+reply.get("characters")+" characters · "+reply.get("elapsed_seconds")+"s";
        }
        if("progress".equals(reply.get("event")))return "Read "+boundedCount(reply.get("completed_chunks"))+" of "+boundedCount(reply.get("total_chunks"))+" source chunks · "+String.valueOf(reply.get("state"));
        String stage=String.valueOf(reply.get("stage"));
        if("callback_received".equals(stage))return "Browser returned · completing ChatGPT sign-in…";
        if("exchanging_code".equals(stage))return "Verifying ChatGPT authorization…";
        if("verifying_identity".equals(stage))return "Verifying ChatGPT account identity…";
        if("saving_connection".equals(stage))return "Saving ChatGPT connection…";
        return "Complete ChatGPT sign-in in your browser…";
    }
    static Map<String,Object> parseReply(ScriptEngine engine,byte[] bytes)throws Exception{engine.put("payload",new String(bytes,StandardCharsets.UTF_8));Object reply=engine.eval("Java.asJSONCompatible(JSON.parse(payload))");if(!(reply instanceof Map))throw new IOException("Invalid helper response");return (Map<String,Object>)reply;}
    static int boundedCount(Object value){
        if(!(value instanceof Number))throw new IllegalArgumentException("Invalid call count response");
        double number=((Number)value).doubleValue();if(!Double.isFinite(number)||number!=Math.rint(number)||number<0||number>Integer.MAX_VALUE)throw new IllegalArgumentException("Invalid call count response");
        return (int)number;
    }
    static Map<String,Object> approvedRequest(Map<String,Object> request,Map<String,Object> preview){
        int needed=boundedCount(preview.get("required_calls"));
        if((Boolean.FALSE.equals(preview.get("can_send"))||Boolean.FALSE.equals(preview.get("feasible"))))throw new IllegalArgumentException("Request is not ready for approval");
        Map<String,Object> approved=new LinkedHashMap<>(request);approved.put("action","request");approved.put("approved_max_calls",Integer.valueOf(needed));
        approved.put("approved_recipient",preview.get("recipient"));approved.put("approved_model",preview.get("resolved_model"));
        if(preview.get("transport_hash") instanceof String)approved.put("approved_transport_hash",preview.get("transport_hash"));
        if(preview.get("review_binding_hash") instanceof String)approved.put("approved_review_hash",preview.get("review_binding_hash"));
        return approved;
    }
    static String outgoingSummary(Map<String,Object> project){
        if(project==null)return "No derived source records. Selected images will be sent as images.";
        StringBuilder text=new StringBuilder("All retained source records listed below will be sent, including cell values, formulas, cached errors, drawing text, and draft questions. Scientific interpretation remains subject to review.\n");
        Map provenance=(Map)project.get("provenance");
        Object selection=provenance.get("selection_scope");if(selection instanceof Map){Map scope=(Map)selection;text.append("\nFolder intake status: ").append(scope.get("status"));for(Object entry:(List)scope.get("entries")){Map e=(Map)entry;if(!"inventoried".equals(e.get("status")))text.append("\n  ").append(e.get("display_path")).append(" — ").append(e.get("status")).append(": ").append(e.get("reason"));}}
        for(Object item:(List)provenance.get("files")){
            Map file=(Map)item;text.append("\n").append(file.get("name"));
            Object sheets=file.get("sheets");
            if(sheets instanceof List)for(Object entry:(List)sheets){Map sheet=(Map)entry;int errors=0;List cells=(List)sheet.get("cells");for(Object cell:cells)if("source-error".equals(((Map)cell).get("value_kind")))errors++;text.append("\n  ").append(sheet.get("name")).append(": ").append(cells.size()).append(" cell records");if(errors>0)text.append(", ").append(errors).append(" cached source errors");}
            if(file.get("pages") instanceof List)text.append("\n  PDF pages: ").append(((List)file.get("pages")).size());if(file.get("records") instanceof List)text.append("\n  Extracted text records: ").append(((List)file.get("records")).size());if(file.get("extraction_status")!=null)text.append("\n  Extraction status: ").append(file.get("extraction_status"));if(file.get("parse_issues") instanceof List)for(Object issue:(List)file.get("parse_issues")){Map warning=(Map)issue;text.append("\n  ").append(warning.get("status")).append(": ").append(warning.get("reason"));}
            if(file.get("parts") instanceof List)text.append("\n  ").append(((List)file.get("parts")).size()).append(" workbook package parts inventoried");
        }
        Object workspace=project.get("workspace_model");if(workspace instanceof Map){Map current=(Map)workspace;text.append("\n\nCurrent workspace model: ").append(current.get("name")).append(" · ").append(current.get("model_type")).append(" · ").append(current.get("node_count")).append(" nodes. Its complete legacy XML, parameters, tables, expressions and settings will be sent for suggestions only.");}
        Object unknowns=project.get("unknowns");if(unknowns instanceof List)text.append("\n\nDraft questions: ").append(((List)unknowns).size());
        text.append("\n\nUse Inspect source records to read the individual records before approving transmission.");
        return text.toString();
    }
    void showSourceRecords(){showSourceRecords(project);}
    void showSourceRecords(Map<String,Object> inspected){
        if(inspected==null){JOptionPane.showMessageDialog(this,"No derived source records yet.");return;}
        List<Map> records=new ArrayList<>();List<String[]> rows=new ArrayList<>();
        Map provenance=(Map)inspected.get("provenance");
        for(Object item:(List)provenance.get("files")){
            Map file=(Map)item;
            records.add(file);rows.add(new String[]{String.valueOf(file.get("name")),"File inventory"});
            for(String kind:new String[]{"parts","records","regions","pages","parse_issues","relationships"}){
                Object children=file.get(kind);if(children instanceof List)for(Object child:(List)children){Map record=(Map)child;records.add(record);Object location=record.containsKey("name")?record.get("name"):record.containsKey("line")?"Line "+record.get("line"):record.containsKey("page")?"Page "+record.get("page"):record.containsKey("status")?record.get("status"):"Selected region or relationship";rows.add(new String[]{String.valueOf(file.get("name")),String.valueOf(location)});}
            }
            Object sheets=file.get("sheets");if(sheets instanceof List)for(Object entry:(List)sheets){Map sheet=(Map)entry;for(Object cell:(List)sheet.get("cells")){Map record=(Map)cell;records.add(record);rows.add(new String[]{String.valueOf(file.get("name")),String.valueOf(sheet.get("name"))+" · "+String.valueOf(record.get("cell"))});}}
        }
        Object workspace=inspected.get("workspace_model");if(workspace instanceof Map){records.add((Map)workspace);rows.add(new String[]{String.valueOf(((Map)workspace).get("name")),"Reviewed workspace model snapshot"});}
        javax.swing.table.DefaultTableModel model=new javax.swing.table.DefaultTableModel(rows.toArray(new Object[0][]),new String[]{"Source","Record"}){public boolean isCellEditable(int row,int col){return false;}};
        JTable table=new JTable(model);table.setAutoCreateRowSorter(true);JTextArea detail=new JTextArea();detail.setEditable(false);detail.setLineWrap(true);detail.setWrapStyleWord(true);
        table.getSelectionModel().addListSelectionListener(e->{int selected=table.getSelectedRow();if(selected>=0){Map record=records.get(table.convertRowIndexToModel(selected));if(record.containsKey("sheets"))detail.setText(outgoingSummary(inspected));else {String full=json(record);detail.setText(full.length()>64000?full.substring(0,64000)+"\n[Display excerpt: first 64,000 characters. The complete record remains in the prepared source data.]":full);}detail.setCaretPosition(0);}});
        JDialog dialog=new JDialog(app.frmMain,"Selected source records",false);JSplitPane split=new JSplitPane(JSplitPane.VERTICAL_SPLIT,new JScrollPane(table),new JScrollPane(detail));split.setResizeWeight(0.55);dialog.add(split);dialog.setSize(850,650);dialog.setLocationRelativeTo(app.frmMain);dialog.setVisible(true);
    }
    static String friendlyError(Object error){
        if(error instanceof Map){Map detail=(Map)error;Object description=detail.get("message");if(description instanceof String){String text=(String)description;Object category=detail.get("category"),requestId=detail.get("request_id");if(category instanceof String&&((String)category).matches("[a-z0-9_]{1,100}"))text+="\nReason: "+category;if(requestId instanceof String&&((String)requestId).matches("[A-Za-z0-9_-]{6,160}"))text+="\nRequest ID: "+requestId;return text;}}
        String category=String.valueOf(error);
        if(category.startsWith("invalid_model")||category.startsWith("invalid_node")||category.startsWith("cyclic_model")||category.startsWith("disconnected_model"))return "The AI proposal did not pass structural checks ("+category+"). Your editable draft is preserved. Describe the affected branch or Retry; no automatic loop was started.";
        if(category.equals("model_chat_stalled"))return "ChatGPT response progress stopped for the configured stall interval. Your editable draft is preserved. Retry starts a fresh request; no automatic retry was started. Adjust AI Workflow → AI stall timeout if needed.";
        if(category.matches("[a-z0-9_]{1,100}"))System.err.println("AI Workflow error category="+category);
        if(category.equals("derive_workbook_before_sending"))return "The selected workbook must be inspected before it can be sent. Click Inspect sources, then Send.";
        if(category.equals("not_connected"))return "Connect using Continue with ChatGPT, then try Send again. Your model has not changed.";
        if(category.equals("recipient_changed_review_again")||category.equals("model_changed_review_again"))return "The receiving account or model changed. Review a fresh request before sending.";
        if(category.startsWith("invalid_model")||category.startsWith("invalid_question")||category.equals("ignored_probability_requires_chance_parent"))return "ChatGPT returned an unsupported model field or question target. The proposal was not applied. Probabilities belong to branches from chance nodes; ask for a corrected proposal or use the manual editor.";
        if(category.equals("root_cost_unsupported_use_strategy_node")||category.equals("nonterminal_payoff_unsupported_use_cost_or_terminal"))return "The proposal puts an outcome in a field the native engine ignores. Use costs on strategy/chance nodes and payoffs on terminal nodes; root costs must be zero.";
        if(category.endsWith("require_manual_editor"))return "This proposal changes native settings that chat cannot safely edit. Use the manual editor, then send a fresh request.";
        if(category.equals("terminal_cost_unsupported_use_payoff"))return "Terminal costs are unsupported by the original engine. Put supported terminal outcomes in payoff, or move costs to a preceding node. No proposal was applied.";
        if(category.startsWith("edit_would_discard_native"))return "This edit would discard native executable behavior. Keep the affected node and type, or use the manual editor.";
        if(category.contains("selection_changed")||category.contains("source_changed")||category.contains("source_manifest_changed")||category.contains("transport_changed"))return "A selected file changed after inspection. Select it again so the current contents can be reviewed.";
        if(category.equals("inference_call_approval_required")||category.contains("budget")||category.contains("call_limit"))return "Review and approve the current request’s estimated calls before sending.";
        if(category.contains("workspace_scope_denied"))return "This saved sign-in belongs to another workspace. Choose Continue with ChatGPT → Add another account or workspace. Your existing connection has not been replaced.";
        if(category.contains("plan_permission_missing")||category.contains("not_eligible"))return "AI plan usage is unavailable for this account or workspace. Select another eligible connection or review ChatGPT plan/workspace settings. Manual Amua remains available.";
        if(category.contains("invalid_grant")||category.contains("authorization"))return "ChatGPT authorization could not be completed. Choose Continue with ChatGPT to reconnect.";
        if(category.contains("keychain"))return "ChatGPT credentials could not be accessed in macOS Keychain. Allow access for this app and retry.";
        return "ChatGPT could not finish this request. Try again. Your model has not changed.";
    }
    void review(){if(project==null){append(selectionPlan==null?"Inspect sources or open a project first.":folderStatus());return;}JDialog dialog=new JDialog(app.frmMain,"Draft review — calculations remain unavailable until promotion",false);dialog.setSize(1050,740);JTabbedPane tabs=new JTabbedPane();tabs.add("Hierarchy",new JScrollPane(new DraftCanvas(project)));JTextArea details=new JTextArea(outgoingSummary(project));details.setEditable(false);details.setLineWrap(true);tabs.add("Sources and coverage",new JScrollPane(details));
        JPanel questions=new JPanel();questions.setLayout(new BoxLayout(questions,BoxLayout.Y_AXIS));Object us=project.get("unknowns");if(us instanceof List)for(Object o:(List)us){if(!(o instanceof Map))continue;Map q=(Map)o;JPanel row=new JPanel(new BorderLayout());JTextArea label=new JTextArea(String.valueOf(q.get("question"))+" ["+q.get("status")+"]");label.setLineWrap(true);label.setWrapStyleWord(true);label.setEditable(false);row.add(label,BorderLayout.CENTER);JButton answer=new JButton("Answer");answer.addActionListener(e->{String value=JOptionPane.showInputDialog(dialog,"Answer ("+q.get("type")+", "+q.get("unit")+")");if(value==null)return;Map r=req("answer");r.put("project",project);r.put("question_id",q.get("id"));Object typed=value;try{if("mapping".equals(q.get("type"))){ScriptEngine engine=new ScriptEngineManager().getEngineByName("nashorn");engine.put("payload",value);typed=engine.eval("Java.asJSONCompatible(JSON.parse(payload))");}}catch(Exception invalid){JOptionPane.showMessageDialog(dialog,"Enter a JSON object for this mapping answer. Leave it unresolved if the source is unknown.");return;}r.put("value",typed);r.put("unit",q.get("unit"));r.put("expected_revision",project.get("revision"));invoke("workflow",r);});row.add(answer,BorderLayout.EAST);questions.add(row);}tabs.add("Clarifications",new JScrollPane(questions));dialog.add(tabs);JPanel actions=new JPanel();button(actions,"Inspect source records",this::showSourceRecords);button(actions,text("preview_synthetic_module"),()->workflow("preview-synthetic"));dialog.add(actions,BorderLayout.SOUTH);dialog.setLocationRelativeTo(app.frmMain);dialog.setVisible(true);}
    void preview(Map<String,Object> proposal){
        String xml=String.valueOf(proposal.get("candidate_xml"));JTextArea description=new JTextArea(String.valueOf(proposal.get("scope"))+"\nExpected cost: "+proposal.get("expected_total_lkr")+" LKR\n\n"+proposal.get("comparison_status")+"\n\n"+xml,18,60);description.setEditable(false);description.setLineWrap(true);description.setWrapStyleWord(true);
        if(JOptionPane.showConfirmDialog(this,new JScrollPane(description),"Review scoped synthetic module",JOptionPane.OK_CANCEL_OPTION)!=JOptionPane.OK_OPTION)return;
        final Map<String,Object> bound=project;final Object revision=project.get("revision");final long token=epoch.get();status.setText("Validating isolated calculation…");
        new SwingWorker<Path,Void>(){
            protected Path doInBackground()throws Exception{
                Path dir=Files.createTempDirectory(Paths.get(System.getProperty("amua.support")),"module-review-");Path file=dir.resolve("synthetic-scoped.amua");Files.write(file,xml.getBytes(StandardCharsets.UTF_8));
                String resources=System.getProperty("amua.resources");ProcessBuilder builder=new ProcessBuilder(javaExecutable(resources),"-Duser.dir="+dir,"-Damua.support="+dir,"-cp",resources+"/Amua_0.3.6.jar","v21.ValidateModule",file.toString(),String.valueOf(proposal.get("expected_total_lkr")));builder.directory(dir.toFile());builder.redirectError(ProcessBuilder.Redirect.to(nullDevice()));Process p=builder.start();process=p;
                if(!p.waitFor(30,java.util.concurrent.TimeUnit.SECONDS)){p.destroyForcibly();throw new IOException("Engine verification timed out");}
                if(p.exitValue()!=0)throw new IOException("Original-engine validation or arithmetic comparison failed");return file;
            }
            protected void done(){if(token!=epoch.get()||project!=bound||!Objects.equals(revision,project.get("revision")))return;process=null;try{Path file=get();status.setText("Scoped synthetic module validated");JFileChooser chooser=new JFileChooser();chooser.setSelectedFile(new File("synthetic-scoped.amua"));if(chooser.showSaveDialog(WorkflowPanel.this)!=JFileChooser.APPROVE_OPTION)return;Path target=chooser.getSelectedFile().toPath();if(!target.toString().toLowerCase().endsWith(".amua"))throw new IOException("Use .amua for this scoped calculation");if(Files.exists(target))throw new IOException("Choose a new file to preserve existing models");Files.copy(file,target);app.openModel(target.toFile());append("Validated synthetic first-year subtotal opened as a new calculation. Full project and unresolved comparator remain separate.");}catch(Exception e){append("Module not promoted: "+(e.getCause()!=null?e.getCause().getMessage():e.getMessage()));}}
        }.execute();
    }
    base.AmuaModel model(){try{java.lang.reflect.Field f=frmMain.class.getDeclaredField("curModel");f.setAccessible(true);return (base.AmuaModel)f.get(app);}catch(Exception e){return null;}}
    void balance(){if(model()==null)return;if(model().type!=0){append("Balanced layout currently supports decision trees. Markov manual layout remains available.");return;}model().panelTree.ocd("Balance tree",false);}
    public static String json(Object o){if(o==null)return "null";if(o instanceof Map){List<String> a=new ArrayList<>();for(Object entry:((Map)o).entrySet()){Map.Entry e=(Map.Entry)entry;a.add(json(String.valueOf(e.getKey()))+":"+json(e.getValue()));}return "{"+String.join(",",a)+"}";}if(o instanceof Iterable){List<String>a=new ArrayList<>();for(Object v:(Iterable)o)a.add(json(v));return "["+String.join(",",a)+"]";}if(o instanceof Number||o instanceof Boolean)return o.toString();String s=o.toString();StringBuilder b=new StringBuilder("\"");for(char c:s.toCharArray()){switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default:if(c<32)b.append(String.format("\\u%04x",(int)c));else b.append(c);}}return b.append('"').toString();}
    static final class DraftCanvas extends JPanel {
        final List<Map> nodes=new ArrayList<>();final Map<String,List<Map>> children=new HashMap<>();final Map<String,Point> positions=new HashMap<>();int nextY=60,maxX=0;
        DraftCanvas(Map project){Object graph=project.get("graph");Object ns=graph instanceof Map?((Map)graph).get("nodes"):null;if(ns instanceof List)for(Object n:(List)ns)if(n instanceof Map){Map m=(Map)n;nodes.add(m);String parent=String.valueOf(m.get("parent"));children.computeIfAbsent(parent,k->new ArrayList<>()).add(m);}for(Map n:nodes)if(n.get("parent")==null||"".equals(n.get("parent")))place(n,0);setPreferredSize(new Dimension(maxX+500,nextY+100));setBackground(Color.WHITE);setToolTipText("Presentation relationships are not executable probability edges. Click a node for full details.");addMouseListener(new MouseAdapter(){public void mouseClicked(MouseEvent event){for(Map n:nodes){Point p=positions.get(String.valueOf(n.get("id")));if(p!=null&&new Rectangle(p.x,p.y-28,230,68).contains(event.getPoint())){JTextArea detail=new JTextArea(json(n),14,55);detail.setLineWrap(true);detail.setWrapStyleWord(true);detail.setEditable(false);JOptionPane.showMessageDialog(DraftCanvas.this,new JScrollPane(detail),"Presentation node — source meaning requires review",JOptionPane.INFORMATION_MESSAGE);break;}}}});}
        int place(Map n,int depth){String id=String.valueOf(n.get("id"));List<Map> cs=children.getOrDefault(id,Collections.emptyList());int first=nextY,last=nextY;if(cs.isEmpty())nextY+=96;else{boolean initial=true;for(Map c:cs){int y=place(c,depth+1);if(initial){first=y;initial=false;}last=y;}}int y=(first+last)/2;positions.put(id,new Point(50+depth*300,y));maxX=Math.max(maxX,50+depth*300);return y;}
        protected void paintComponent(Graphics graphics){super.paintComponent(graphics);Graphics2D g=(Graphics2D)graphics.create();g.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);for(Map n:nodes){Point p=positions.get(String.valueOf(n.get("id"))),parent=positions.get(String.valueOf(n.get("parent")));if(p==null)continue;if(parent!=null){g.setColor(new Color(155,170,180));g.drawLine(parent.x+230,parent.y,p.x,p.y);}g.setColor(new Color(240,246,249));g.fillRoundRect(p.x,p.y-28,230,68,10,10);g.setColor(new Color(30,66,85));g.drawRoundRect(p.x,p.y-28,230,68,10,10);String label=String.valueOf(n.get("label"));int line=0;String current="";for(String word:label.split(" ")){if(g.getFontMetrics().stringWidth(current+word)>210){if(line<3)g.drawString(current,p.x+10,p.y-9+line*16);line++;current="";if(line>=3){g.drawString("… click for full details",p.x+10,p.y+37);break;}}current+=word+" ";}if(line<3)g.drawString(current,p.x+10,p.y-9+line*16);}g.dispose();}
    }
}
