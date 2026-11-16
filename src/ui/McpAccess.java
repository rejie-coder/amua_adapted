package v21;

import gui.frmMain;
import javax.swing.*;
import javax.swing.event.MenuEvent;
import javax.swing.event.MenuListener;
import java.awt.*;
import java.awt.datatransfer.StringSelection;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Local MCP access and portable, client-specific connection walkthroughs. */
public final class McpAccess {
    public static final String SERVER="amua_324";
    public static final String[] CLIENTS={"Hermes","Codex","Claude Code","DeepSeek harness","OpenClaw","Any MCP client"};
    private static JDialog dialog;
    private McpAccess() {}

    public static Path support(){return Paths.get(System.getProperty("amua.support",System.getProperty("user.home")+"/Library/Application Support/Amua-v3.3.2"));}
    public static boolean isEnabled(){
        Path path=support().resolve("mcp-access.properties");
        if(!Files.exists(path))return true;
        if(Files.isSymbolicLink(path))return false;
        try(InputStream in=Files.newInputStream(path)){
            Properties properties=new Properties();properties.load(in);return "true".equals(properties.getProperty("enabled"));
        }catch(IOException error){return false;}
    }
    public static void setEnabled(boolean enabled)throws IOException{
        Path directory=support(),path=directory.resolve("mcp-access.properties");
        if(Files.isSymbolicLink(directory)||Files.isSymbolicLink(path))throw new IOException("Choose a normal local app support directory.");
        Files.createDirectories(directory);
        Path temporary=Files.createTempFile(directory,"mcp-access-",".tmp");
        try {
            Properties properties=new Properties();properties.setProperty("enabled",String.valueOf(enabled));
            try(OutputStream out=Files.newOutputStream(temporary)){properties.store(out,"Amua local MCP access");}
            Files.move(temporary,path,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
        }finally{Files.deleteIfExists(temporary);}
    }
    public static void install(frmMain app){
        JMenuBar bar=app.frmMain.getJMenuBar();JMenu access=new JMenu("MCP Access");
        access.setToolTipText("Connect Hermes, Codex, Claude Code or another AI agent");
        JMenuItem open=new JMenuItem("Connection walkthrough…");open.addActionListener(e->show(app.frmMain));access.add(open);
        // A JMenu remains visible in the native macOS menu bar; selecting it acts
        // as the requested access button. The menu item is a keyboard fallback.
        access.addMenuListener(new MenuListener(){
            public void menuSelected(MenuEvent event){if(!GraphicsEnvironment.isHeadless())SwingUtilities.invokeLater(()->{MenuSelectionManager.defaultManager().clearSelectedPath();show(app.frmMain);});}
            public void menuDeselected(MenuEvent event){}
            public void menuCanceled(MenuEvent event){}
        });
        int index=bar.getMenuCount();String help=app.language.base.getString("menu.help");
        for(int i=0;i<bar.getMenuCount();i++)if(bar.getMenu(i)!=null&&help.equals(bar.getMenu(i).getText())){index=i;break;}
        bar.add(access,index);bar.revalidate();bar.repaint();
    }
    private static void show(JFrame owner){
        if(dialog!=null&&dialog.isDisplayable()){dialog.setVisible(true);dialog.toFront();return;}
        dialog=new JDialog(owner,"Amua 3.3.2 · MCP connection walkthrough",false);
        dialog.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);dialog.setContentPane(createPanel(owner));
        dialog.setSize(900,690);dialog.setMinimumSize(new Dimension(720,540));dialog.setLocationRelativeTo(owner);dialog.setVisible(true);
    }
    static JTextArea prose(String value){JTextArea text=new JTextArea(value);text.setEditable(false);text.setLineWrap(true);text.setWrapStyleWord(true);text.setOpaque(false);text.setBorder(BorderFactory.createEmptyBorder(8,8,8,8));return text;}
    public static JPanel createPanel(JFrame owner){
        JPanel root=new JPanel(new BorderLayout(10,10));root.setBorder(BorderFactory.createEmptyBorder(16,16,16,16));
        JPanel heading=new JPanel(new BorderLayout());JLabel title=new JLabel("Connect an AI agent to Amua");title.setFont(title.getFont().deriveFont(Font.BOLD,22f));heading.add(title,BorderLayout.NORTH);
        heading.add(prose("Your agent can inspect, edit, validate and run models using Amua’s original engine. The agent uses its own AI provider. Amua’s built-in ChatGPT sign-in is a separate connection."),BorderLayout.CENTER);root.add(heading,BorderLayout.NORTH);
        JTabbedPane steps=new JTabbedPane();
        JPanel access=new JPanel(new BorderLayout(8,8));JCheckBox enabled=new JCheckBox("Allow local MCP agent access",isEnabled());
        JLabel feedback=new JLabel("Server: "+SERVER+" · Engine 0.3.6 · MCP stdio");
        JLabel accessState=new JLabel(isEnabled()?"Access enabled · local stdio connection":"Access disabled");JPanel switchPanel=new JPanel(new GridLayout(0,1,4,4));switchPanel.add(enabled);switchPanel.add(accessState);access.add(switchPanel,BorderLayout.NORTH);
        enabled.addActionListener(e->{try{setEnabled(enabled.isSelected());accessState.setText(enabled.isSelected()?"Access enabled · local stdio connection":"Access disabled · agent tool calls will be rejected");}catch(IOException error){enabled.setSelected(isEnabled());accessState.setText("Could not save access setting: "+error.getMessage());}});
        access.add(prose("1. Keep Amua 3.3.2 open on this Mac.\n\n2. Allow access above, then choose your agent on the next tab.\n\n3. Add the supplied local stdio server to your agent and start a new agent session.\n\nThe connection is local: there is no public server address or API key to paste into Amua. Your agent must run on this Mac, or use a local MCP execution bridge.\n\nYou can switch access off here at any time. Agent requests then stop being accepted; your models stay open."),BorderLayout.CENTER);steps.addTab("1 · Access",access);
        JPanel setup=new JPanel(new BorderLayout(8,8));JComboBox<String> client=new JComboBox<>(CLIENTS);client.setName("MCP agent");setup.add(client,BorderLayout.NORTH);
        JTextArea instructions=prose(guide(CLIENTS[0]));instructions.setRows(5);JTextArea payload=new JTextArea(configuration(CLIENTS[0],resources()),13,70);payload.setEditable(false);payload.setFont(new Font(Font.MONOSPACED,Font.PLAIN,12));payload.setName("MCP setup configuration");
        JPanel body=new JPanel(new BorderLayout());body.add(instructions,BorderLayout.NORTH);body.add(new JScrollPane(payload),BorderLayout.CENTER);setup.add(body,BorderLayout.CENTER);
        client.addActionListener(e->{String selected=String.valueOf(client.getSelectedItem());instructions.setText(guide(selected));payload.setText(configuration(selected,resources()));payload.setCaretPosition(0);});
        JPanel copy=new JPanel(new FlowLayout(FlowLayout.LEFT));JButton copySetup=new JButton("Copy setup");copySetup.addActionListener(e->copy(payload.getText(),feedback));copy.add(copySetup);JButton copyLaunch=new JButton("Copy launch command");copyLaunch.addActionListener(e->copy(launchCommand(resources()),feedback));copy.add(copyLaunch);
        JButton save=new JButton("Save setup…");save.addActionListener(e->{JFileChooser chooser=new JFileChooser();chooser.setSelectedFile(new File("Amua-3.3.2-MCP-setup.txt"));if(chooser.showSaveDialog(owner)!=JFileChooser.APPROVE_OPTION)return;try{Files.write(chooser.getSelectedFile().toPath(),(guide(String.valueOf(client.getSelectedItem()))+"\n\n"+payload.getText()+"\n\n"+firstTask()).getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);feedback.setText("Setup saved");}catch(IOException error){JOptionPane.showMessageDialog(owner,"Choose a new file name. "+error.getMessage(),"Setup not saved",JOptionPane.INFORMATION_MESSAGE);}});copy.add(save);setup.add(copy,BorderLayout.SOUTH);steps.addTab("2 · Agent setup",setup);
        JPanel verify=new JPanel(new BorderLayout(8,8));JTextArea result=prose("Register the server in your agent, then ask it to call amua_status and amua_inspect. A successful local test checks the server and this app; your agent’s tool list confirms its own connection.\n\n"+lastActivity());verify.add(new JScrollPane(result),BorderLayout.CENTER);
        JButton test=new JButton("Test local connection");test.addActionListener(e->{test.setEnabled(false);result.setText("Checking the local server and Amua…");new SwingWorker<String,Void>(){
            protected String doInBackground()throws Exception{
                Process process=new ProcessBuilder(WorkflowPanel.pythonExecutable(resources()),"-B",resources()+"/amua_mcp.py","--self-test").redirectError(ProcessBuilder.Redirect.to(WorkflowPanel.nullDevice())).start();
                ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[2048];int n;while((n=process.getInputStream().read(buffer))!=-1){if(out.size()+n>64000){process.destroyForcibly();throw new IOException("Test response too large");}out.write(buffer,0,n);}if(process.waitFor()!=0)throw new IOException("The local test could not finish.");return new String(out.toByteArray(),StandardCharsets.UTF_8);
            }
            protected void done(){test.setEnabled(true);try{String data=get();javax.script.ScriptEngine engine=new javax.script.ScriptEngineManager().getEngineByName("nashorn");engine.put("payload",data);Map checked=(Map)engine.eval("Java.asJSONCompatible(JSON.parse(payload))");result.setText(String.valueOf(checked.get("message"))+"\nTools available: "+checked.get("tools_available")+"\n\n"+lastActivity());}catch(Exception error){result.setText("Connection test could not complete. Check that access is enabled and that this app is still open.\n"+lastActivity());}}
        }.execute();});verify.add(test,BorderLayout.SOUTH);steps.addTab("3 · Verify",verify);
        JPanel task=new JPanel(new BorderLayout());task.add(prose(firstTask()),BorderLayout.CENTER);JButton copyTask=new JButton("Copy first task");copyTask.addActionListener(e->copy(firstTask(),feedback));task.add(copyTask,BorderLayout.SOUTH);steps.addTab("4 · First task",task);root.add(steps,BorderLayout.CENTER);
        root.add(feedback,BorderLayout.SOUTH);return root;
    }
    private static String resources(){return System.getProperty("amua.resources","");}
    static String shell(String value){if(WorkflowPanel.isWindows())return "\'"+value.replace("\'","\'\'")+"\'";return "'"+value.replace("'","'\"'\"'")+"'";}
    public static String launchCommand(String resources){return (WorkflowPanel.isWindows()?"& ":"")+shell(WorkflowPanel.pythonExecutable(resources))+" -B "+shell(resources+"/amua_mcp.py");}
    public static String serverJson(String resources){Map<String,Object> entry=new LinkedHashMap<>();entry.put("command",WorkflowPanel.pythonExecutable(resources));entry.put("args",Arrays.asList("-B",resources+"/amua_mcp.py"));return WorkflowPanel.json(entry);}
    public static String configuration(String client,String resources){
        String executable=WorkflowPanel.pythonExecutable(resources),script=resources+"/amua_mcp.py",command=launchCommand(resources);
        if("Codex".equals(client))return "codex mcp add "+SERVER+" -- "+(WorkflowPanel.isWindows()?command.substring(2):command);
        if("Claude Code".equals(client))return "claude mcp add --transport stdio --scope user "+SERVER+" -- "+(WorkflowPanel.isWindows()?command.substring(2):command);
        if("OpenClaw".equals(client))return "openclaw mcp set "+SERVER+" "+shell(serverJson(resources))+"\nopenclaw mcp probe "+SERVER;
        if("Hermes".equals(client))return "mcp_servers:\n  "+SERVER+":\n    command: "+WorkflowPanel.json(executable)+"\n    args: [\"-B\", "+WorkflowPanel.json(script)+"]\n    timeout: 120\n";
        return "{\n  \"mcpServers\": {\n    \""+SERVER+"\": "+serverJson(resources)+"\n  }\n}";
    }
    public static String guide(String client){
        if("Hermes".equals(client))return "Merge this entry into ~/.hermes/config.yaml under mcp_servers, preserving your other servers. Restart your Hermes session and ask it to use Amua.\nGuide: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp";
        if("Codex".equals(client))return "Run this registration command in Terminal on this Mac. Confirm it with codex mcp list, then start a new Codex session and check /mcp. It uses a new server name, preserving an existing amua connection.\nGuide: https://developers.openai.com/codex/mcp";
        if("Claude Code".equals(client))return "Run this command in Terminal to register the server at user scope. Start a new Claude Code session and check /mcp for amua_324.\nGuide: https://code.claude.com/docs/en/mcp";
        if("OpenClaw".equals(client))return "For current OpenClaw native MCP support, stop your Gateway before changing the MCP registry. Run the setup and probe commands, then restart the Gateway/session. Older builds may need an MCP adapter such as mcporter; use the generic stdio launch details for that adapter.\nGuide: https://docs.openclaw.ai/cli/mcp/registry";
        if("DeepSeek harness".equals(client))return "Use a DeepSeek-backed harness that supports MCP tools. Add this common mcpServers entry, or copy its command and args into your harness’s stdio server settings. Restart/reload that harness and list tools. DeepSeek is the model provider; the harness supplies MCP support.";
        return "In an MCP-capable client on this Mac, add a local stdio server using this common JSON format. If its configuration format differs, copy the command and argument fields into its server settings. Restart/reload the client and list tools. Use the bundled executable, not a system Python installation.";
    }
    public static String firstTask(){return "Use the amua_324 MCP server for my requested Amua work. Call amua_status, then amua_inspect and amua_model_summary when a model is open. Report the active model and missing inputs before editing. Use observed controls and inspect dialogs after actions. Preserve the original engine’s validation and calculations. Save new work to a new .amua path unless I request replacement. Run amua_validate_model before amua_run_model; inspect console/status for actual analysis completion. Do not invent scientific inputs. Start with inspection only.";}
    static void copy(String value,JLabel state){try{Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new StringSelection(value),null);state.setText("Copied");}catch(Exception error){state.setText("Clipboard unavailable; select the setup text and copy it manually.");}}
    static String lastActivity(){
        try {
            Path path=support().resolve("mcp-last-client.json");if(!Files.exists(path)||Files.size(path)>16384)return "No agent handshake recorded yet.";
            javax.script.ScriptEngine engine=new javax.script.ScriptEngineManager().getEngineByName("nashorn");engine.put("payload",new String(Files.readAllBytes(path),StandardCharsets.UTF_8));
            Map data=(Map)engine.eval("Java.asJSONCompatible(JSON.parse(payload))");
            return "Last client: "+data.get("client")+"\nLast activity: "+data.get("method")+"\nWhen: "+data.get("at_utc");
        }catch(Exception error){return "Agent activity is unavailable.";}
    }
}
