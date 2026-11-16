
var System=Java.type('java.lang.System');
System.setProperty('amua.support','/Users/rejie/Desktop/Amua/3.2.4/build/headless-check');
System.setProperty('amua.resources','/Users/rejie/Desktop/Amua/3.2.4/Amua.app/Contents/Resources');
var Files=Java.type('java.nio.file.Files'), Paths=Java.type('java.nio.file.Paths');
Files.createDirectories(Paths.get('/Users/rejie/Desktop/Amua/3.2.4/build/headless-check/bridge'));
var src=String(new java.lang.String(Files.readAllBytes(Paths.get('/Users/rejie/Desktop/Amua/3.2.4/src/native-support/bootstrap.js')),java.nio.charset.StandardCharsets.UTF_8));
var stop=src.lastIndexOf('\nEventQueue.invokeLater(function() {');
if(stop<0) throw new Error('Bootstrap startup boundary missing');
load({script:src.substring(0,stop),name:'bootstrap-functions.js'});
var Main=Java.type('gui.frmMain');
var mainClass=Main.class;
['curModel','modelList','console','tabbedPaneCanvas','mntmDecisionTree','mntmMarkovModel','mntmAboutAmua'].forEach(function(n){mainClass.getDeclaredField(n);});
var button=new (Java.type('javax.swing.JButton'))('Test button');
button.addNotify();
var buttonID=componentId(button);
if(describe(button).text!=='Test button') throw new Error('Button description failed');
var textField=new (Java.type('javax.swing.JTextField'))('before');
textField.addNotify();
var id=componentId(textField);
dispatch('set_text',{id:id,text:'after'});
EventQueue.invokeAndWait(function(){});
if(String(textField.getText())!=='after') throw new Error('Text update failed');
var combo=new (Java.type('javax.swing.JComboBox'))(Java.to(['A','B'],'java.lang.String[]'));
combo.addNotify();
dispatch('select',{id:componentId(combo),index:1});
EventQueue.invokeAndWait(function(){});
if(combo.getSelectedIndex()!==1) throw new Error('Selection failed');
var table=new (Java.type('javax.swing.JTable'))(2,2);table.addNotify();
var tid=componentId(table);dispatch('set_cell',{id:tid,row:1,column:0,value:'value'});
EventQueue.invokeAndWait(function(){});
if(dispatch('table',{id:tid}).rows[1][0]!=='value') throw new Error('Table access failed');
try {dispatch('set_text',{id:buttonID,text:'forbidden'});throw new Error('Unsafe control accepted');}
catch(e) {if(String(e).indexOf('not editable')<0) throw e;}
try {dispatch('unknown_operation',{});throw new Error('Unknown operation accepted');}
catch(e) {if(String(e).indexOf('Unknown AMUA operation')<0) throw e;}
var sample=Paths.get('/Users/rejie/Desktop/Amua/3.2.4/build/headless-check/atomic.json');writeJSON(sample,{ok:true});
if(readJSON(sample).ok!==true) throw new Error('Atomic JSON roundtrip failed');

var model=new (Java.type('base.AmuaModel'))();model.name='headless-roundtrip';
var xml=Paths.get('/Users/rejie/Desktop/Amua/3.2.4/build/headless-check/model.amua');
var context=Java.type('javax.xml.bind.JAXBContext').newInstance(Java.to([model.getClass()],'java.lang.Class[]'));
context.createMarshaller().marshal(model,xml.toFile());
var decoded=context.createUnmarshaller().unmarshal(xml.toFile());
if(String(decoded.name)!=='headless-roundtrip') throw new Error('JAXB model roundtrip failed');
if(!String('model.amua').endsWith('.amua')) throw new Error('String extension check failed');
var menuBar=new (Java.type('javax.swing.JMenuBar'))();
var menu=new (Java.type('javax.swing.JMenu'))('Menu');
var menuEntry=new (Java.type('javax.swing.JMenuItem'))('Item');
menu.add(menuEntry);menuBar.add(menu);menuBar.addNotify();
if(!liveComponent(menuEntry)) throw new Error('Unopened menu item is incorrectly unavailable');
var invoked=false;menuEntry.addActionListener(function(){invoked=true;});
dispatch('click',{id:componentId(menuEntry)});EventQueue.invokeAndWait(function(){});
if(!invoked) throw new Error('Menu item invocation failed');
var spinner=new (Java.type('javax.swing.JSpinner'))(new (Java.type('javax.swing.SpinnerNumberModel'))(new java.lang.Double(1.5),new java.lang.Double(0),new java.lang.Double(10),new java.lang.Double(.1)));
spinner.addNotify();dispatch('select',{id:componentId(spinner),value:2.75});EventQueue.invokeAndWait(function(){});
if(Number(spinner.getValue())!==2.75) throw new Error('Decimal spinner value lost');
var tableModel=new (Java.type('javax.swing.table.DefaultTableModel'))(Java.to([Java.to([new java.lang.Double(1.5),new java.lang.Boolean(false)],'java.lang.Object[]')],'java.lang.Object[][]'),Java.to(['number','boolean'],'java.lang.Object[]'));
var typedTable=new (Java.type('javax.swing.JTable'))(tableModel);typedTable.addNotify();
dispatch('set_cell',{id:componentId(typedTable),row:0,column:0,value:3.25});
dispatch('set_cell',{id:componentId(typedTable),row:0,column:1,value:true});EventQueue.invokeAndWait(function(){});
if(Number(typedTable.getValueAt(0,0))!==3.25 || String(typedTable.getValueAt(0,0).getClass().getName())!=='java.lang.Double') throw new Error('Numeric cell type lost');
if(String(typedTable.getValueAt(0,1).getClass().getName())!=='java.lang.Boolean') throw new Error('Boolean cell type lost');
var source=Paths.get('/Users/rejie/Desktop/Amua/3.2.4/build/headless-check/new.tmp'),destination=Paths.get('/Users/rejie/Desktop/Amua/3.2.4/build/headless-check/fallback.amua');
Files.deleteIfExists(destination);Files.write(source,new java.lang.String('new-data').getBytes(UTF8));
publishNewFile(source,destination,function(){throw new java.lang.UnsupportedOperationException('test unsupported links');});
if(String(new java.lang.String(Files.readAllBytes(destination),UTF8))!=='new-data') throw new Error('No-link save fallback failed');
Files.write(source,new java.lang.String('replacement').getBytes(UTF8));
try {publishNewFile(source,destination);throw new Error('Existing destination was replaced');}
catch(e) {if(String(e).indexOf('FileAlreadyExists')<0) throw e;}
if(String(new java.lang.String(Files.readAllBytes(destination),UTF8))!=='new-data') throw new Error('Existing data lost');
if(String(operations[lastAction.id].state)!=='completed') throw new Error('Operation result tracking failed');
var gated=null,ranDisabled=false;
EventQueue.invokeAndWait(function(){
 gated=later('set_text',function(){ranDisabled=true;});
 Java.type('v21.McpAccess').setEnabled(false);
});
EventQueue.invokeAndWait(function(){});
if(ranDisabled || operations[gated.operation_id].state!=='error') throw new Error('Disabled access allowed queued action');
Java.type('v21.McpAccess').setEnabled(true);
print('PASS: runtime/JAR loading, actual Swing controls/menu actions, control rejection, atomic JSON, AMUA XML roundtrip');

System.exit(0);
