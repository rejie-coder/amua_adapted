/* AMUA 0.3.6 desktop bootstrap and local control bridge.
 * Executes inside the bundled Java 8 VM. All Swing operations run on the EDT.
 * No network listener, Java agent, accessibility permission or screen recording.
 */
var System = Java.type('java.lang.System');
var Files = Java.type('java.nio.file.Files');
var Paths = Java.type('java.nio.file.Paths');
var File = Java.type('java.io.File');
var UTF8 = Java.type('java.nio.charset.StandardCharsets').UTF_8;
var Copy = Java.type('java.nio.file.StandardCopyOption');
var EventQueue = Java.type('java.awt.EventQueue');
var Window = Java.type('java.awt.Window');
var JFrame = Java.type('javax.swing.JFrame');
var JDialog = Java.type('javax.swing.JDialog');
var Container = Java.type('java.awt.Container');
var JComponent = Java.type('javax.swing.JComponent');
var AbstractButton = Java.type('javax.swing.AbstractButton');
var JMenu = Java.type('javax.swing.JMenu');
var JMenuItem = Java.type('javax.swing.JMenuItem');
var JPopupMenu = Java.type('javax.swing.JPopupMenu');
var JMenuBar = Java.type('javax.swing.JMenuBar');
var JTextComponent = Java.type('javax.swing.text.JTextComponent');
var JLabel = Java.type('javax.swing.JLabel');
var JTable = Java.type('javax.swing.JTable');
var JTabbedPane = Java.type('javax.swing.JTabbedPane');
var JComboBox = Java.type('javax.swing.JComboBox');
var JList = Java.type('javax.swing.JList');
var JSpinner = Java.type('javax.swing.JSpinner');
var JSlider = Java.type('javax.swing.JSlider');
var FocusEvent = Java.type('java.awt.event.FocusEvent');
var MouseEvent = Java.type('java.awt.event.MouseEvent');
var Timer = Java.type('javax.swing.Timer');
var IdentityHashMap = Java.type('java.util.IdentityHashMap');
var UUID = Java.type('java.util.UUID');
var ManagementFactory = Java.type('java.lang.management.ManagementFactory');
var support = String(System.getProperty('amua.support'));
var resources = String(System.getProperty('amua.resources'));
var bridge = Paths.get(support, 'bridge');
var instance = String(UUID.randomUUID());
var app = null, timer = null;
var ids = new IdentityHashMap(), components = {}, nextId = 1;
var lastAction = null, lastHeartbeat = 0;
var operations = {}, operationOrder = [], requestDeadline = null;
var launchArguments = [];
if (typeof arguments !== 'undefined') {
    for (var arg=0;arg<arguments.length;arg++) launchArguments.push(String(arguments[arg]));
}

function readJSON(path) { return JSON.parse(String(new java.lang.String(Files.readAllBytes(path), UTF8))); }
function writeJSON(path, data) {
    var temporary = Paths.get(String(path)+'.tmp');
    Files.write(temporary, new java.lang.String(JSON.stringify(data)).getBytes(UTF8));
    Files.move(temporary, path, Copy.REPLACE_EXISTING, Copy.ATOMIC_MOVE);
}
function field(object, name) {
    var f = object.getClass().getDeclaredField(name);
    f.setAccessible(true);
    return f.get(object);
}
function currentModel() {
    var model = field(app, 'curModel');
    if (model === null) throw new Error('No model is open.');
    return model;
}
function str(value) { return value === null || value === undefined ? null : String(value); }
function componentId(c) {
    var id = ids.get(c);
    if (id === null) { id = 'c'+nextId++; ids.put(c, id); components[id] = c; }
    return String(id);
}
function component(id) {
    var c = components[id];
    if (!c) throw new Error('Unknown component '+id+'. Inspect the app first.');
    if (!liveComponent(c)) throw new Error('Component is no longer displayed. Inspect again.');
    return c;
}
function liveComponent(c) {
    if(c.isDisplayable()) return true;
    if(c instanceof JMenuItem) {
        var parent=c.getParent(),depth=0;
        while(parent!==null && depth++<30) {
            if(parent.isDisplayable()) return true;
            parent=parent instanceof JPopupMenu?parent.getInvoker():parent.getParent();
        }
    }
    return false;
}
function label(c) {
    if (c instanceof AbstractButton || c instanceof JLabel || c instanceof JTextComponent) return str(c.getText());
    if (c instanceof JFrame || c instanceof JDialog) return str(c.getTitle());
    return null;
}
function describe(c) {
    var d = {id:componentId(c), type:String(c.getClass().getName()),
        name:str(c.getName()), enabled:!!c.isEnabled(), visible:!!c.isVisible(),
        showing:!!c.isShowing(), bounds:{x:c.getX(), y:c.getY(), width:c.getWidth(), height:c.getHeight()}};
    var text = label(c);
    if (text !== null) d.text = text.slice(0, 8000);
    if (c instanceof JComponent) d.tooltip = str(c.getToolTipText());
    if (c instanceof AbstractButton) d.selected = !!c.isSelected();
    if (c instanceof JTextComponent) d.editable = !!c.isEditable();
    if (c instanceof JTable) {
        d.rows=c.getRowCount(); d.columns=[];
        for (var j=0;j<c.getColumnCount();j++) d.columns.push(str(c.getColumnName(j)));
        d.selectedRow=c.getSelectedRow();
    }
    if (c instanceof JTabbedPane) {
        d.selectedIndex=c.getSelectedIndex(); d.tabs=[];
        for (var k=0;k<c.getTabCount();k++) d.tabs.push(str(c.getTitleAt(k)));
    }
    if (c instanceof JComboBox) {
        d.selectedIndex=c.getSelectedIndex(); d.options=[];
        for (var v=0;v<Math.min(100,c.getItemCount());v++) d.options.push(str(c.getItemAt(v)));
    }
    if (c instanceof JList) {
        d.selectedIndex=c.getSelectedIndex(); d.options=[];
        for (var a=0;a<Math.min(100,c.getModel().getSize());a++) d.options.push(str(c.getModel().getElementAt(a)));
    }
    if (c instanceof JSpinner || c instanceof JSlider) d.value=str(c.getValue());
    return d;
}
function inspect(params) {
    // Release references held for disposed dialogs while preserving live ids.
    Object.keys(components).forEach(function(id) {
        if(!liveComponent(components[id])) {ids.remove(components[id]);delete components[id];}
    });
    var budget = Math.min(3000, Math.max(1, params.max_nodes || 1000)), count=0;
    var seen = new IdentityHashMap();
    function walk(c) {
        if (count >= budget || seen.containsKey(c)) return null;
        seen.put(c, true); count++;
        var d=describe(c), children=[];
        if (c instanceof JMenu) {
            var menuChildren=c.getMenuComponents();
            for(var m=0;m<menuChildren.length;m++) {var v=walk(menuChildren[m]); if(v) children.push(v);}
        } else if (c instanceof Container) {
            var items=c.getComponents();
            for(var i=0;i<items.length;i++) {var item=walk(items[i]); if(item) children.push(item);}
        }
        if (children.length) d.children=children;
        return d;
    }
    var windows=[], all=Window.getWindows();
    for(var i=0;i<all.length;i++) {
        if (!all[i].isVisible()) continue;
        if (params.window && componentId(all[i]) !== params.window) continue;
        var w=walk(all[i]);
        if (w && all[i] instanceof JDialog) w.modal=!!all[i].isModal();
        if(w) windows.push(w);
    }
    return {windows:windows, nodes:count, truncated:count>=budget, last_action:lastAction};
}
function modelSummary() {
    var m=currentModel();
    var result={name:str(m.name), path:str(m.filepath), type:m.type===0?'decision_tree':'markov',
        unsaved_changes:!!m.unsavedChanges, simulation:m.simType===0?'cohort':'monte_carlo',
        cohort_size:m.cohortSize, threads:m.numThreads, parameters:[],variables:[],dimensions:[]};
    for(var i=0;i<m.parameters.size();i++) {
        var p=m.parameters.get(i); result.parameters.push({name:str(p.name),expression:str(p.expression)});
    }
    for(var v=0;v<m.variables.size();v++) {
        var x=m.variables.get(v); result.variables.push({name:str(x.name),expression:str(x.expression)});
    }
    var ds=m.dimInfo.dimNames;
    if(ds) result.dimensions=Java.from(ds).map(String);
    var nodes=m.type===0?m.tree.nodes:m.markov.nodes;
    result.nodes=[];
    for(var n=0;n<nodes.size();n++) {
        var node=nodes.get(n), nd={index:n,name:str(node.name),type:node.type,
            x:node.xPos,y:node.yPos};
        try{nd.probability=str(node.prob);}catch(ignored){}
        result.nodes.push(nd);
    }
    return result;
}
function status() {
    var runtime=java.lang.Runtime.getRuntime(), models=[];
    if(app!==null) {
        var list=field(app,'modelList');
        for(var i=0;i<list.size();i++) {
            var m=list.get(i); models.push({index:i,name:str(m.name),path:str(m.filepath),
                type:m.type===0?'decision_tree':'markov',unsaved_changes:!!m.unsavedChanges});
        }
    }
    return {running:true,ready:app!==null,instance:instance,
        pid:Number(String(ManagementFactory.getRuntimeMXBean().getName()).split('@')[0]),
        java:String(System.getProperty('java.version')),architecture:String(System.getProperty('os.arch')),
        memory_used_mb:Math.round((runtime.totalMemory()-runtime.freeMemory())/1048576),
        uptime_ms:ManagementFactory.getRuntimeMXBean().getUptime(),models:models,
        responsive:true,last_action:lastAction, heartbeat_ms:Date.now()};
}
function later(name, fn) {
    var pending=operationOrder.filter(function(id){return operations[id] && ['queued','running'].indexOf(operations[id].state)>=0;}).length;
    if(pending>=32) throw new Error('Operation queue is full. Wait for pending actions.');
    var bound=app===null?null:field(app,'curModel'), deadline=requestDeadline||Date.now()+30000;
    var modelBound=['activate','quit','new_model','open_model'].indexOf(name)<0;
    var operation=String(UUID.randomUUID());
    var record={id:operation,action:name,state:'queued'};
    operations[operation]=record;operationOrder.push(operation);
    if(operationOrder.length>40) delete operations[operationOrder.shift()];
    lastAction=record;
    EventQueue.invokeLater(function() {
        record.state='running';lastAction=record;
        try {
            if(name!=='activate'&&name!=='quit'&&!Java.type('v21.McpAccess').isEnabled()) throw new Error('MCP access is disabled in Amua.');
            if(Date.now()>deadline) throw new Error('Queued action expired. Inspect before retrying.');
            if(modelBound && app!==null && field(app,'curModel')!==bound) throw new Error('Active model changed before this action. Inspect before retrying.');
            var result=fn();record.result=result===undefined?null:result;record.state='completed'; }
        catch(e) { record.state='error';record.error=String(e);System.err.println(e.stack||e); }
    });
    return {accepted:true,operation_id:operation,instruction:'Inspect or check status for the result; modal dialogs remain operable.'};
}
function openFile(path) {
    var file=new File(String(path)).getCanonicalFile();
    if (!file.isFile()) throw new Error('Model file does not exist: '+file);
    if (!String(file.getName()).toLowerCase().endsWith('.amua')) throw new Error('Expected an .amua model.');
    var list=field(app,'modelList');
    for(var i=0;i<list.size();i++) {
        if(str(list.get(i).filepath)===String(file.getAbsolutePath())) {
            field(app,'tabbedPaneCanvas').setSelectedIndex(i); return;
        }
    }
    // Upstream openModel catches exceptions internally. Preflight malformed XML,
    // then check its actual outcome and error log rather than assuming success.
    var context=Java.type('javax.xml.bind.JAXBContext').newInstance(Java.to([Java.type('base.AmuaModel').class],'java.lang.Class[]'));
    var decoded=Java.type('base.AtomicModelSave').read(file.toPath());
    if(!(decoded instanceof Java.type('base.AmuaModel'))) throw new Error('Not an AMUA model.');
    var errorLog=field(app,'errorLog'), before=errorLog.errors.size();
    app.openModel(file);
    if(errorLog.errors.size()>before) throw new Error('AMUA could not fully open the model: '+errorLog.errors.get(before));
    var active=field(app,'curModel');
    if(active===null || str(active.filepath)!==String(file.getAbsolutePath()) || !list.contains(active)) {
        throw new Error('AMUA did not open the requested model. See its console.');
    }
    return {opened:true,path:String(file.getAbsolutePath())};
}
function publishNewFile(temporary,destination,link) {
    try {
        if(link) link(destination,temporary);else Files.createLink(destination,temporary);
    } catch(e) {
        // External/network filesystems may not support hard links. CREATE_NEW
        // still prevents replacement, including if a competing save wins a race.
        var options=Java.type('java.nio.file.StandardOpenOption');
        var output=Files.newOutputStream(destination,options.CREATE_NEW,options.WRITE), complete=false;
        try {Files.copy(temporary,output);output.close();complete=true;}
        finally {if(!complete) {try{output.close();}finally{Files.deleteIfExists(destination);}}}
    }
    Files.delete(temporary);
}
function typedValue(value, expected) {
    var name=String(expected.getName());
    if(name==='java.lang.Object') {
        if(typeof value==='number') return Java.type('java.lang.Double').valueOf(String(value));
        if(typeof value==='boolean') return Java.type('java.lang.Boolean').valueOf(value);
        return value===null?null:String(value);
    }
    if(name==='java.lang.String') return value===null?null:String(value);
    if(name==='java.lang.Boolean') {
        if(typeof value!=='boolean') throw new Error('This control requires a boolean.');
        return Java.type('java.lang.Boolean').valueOf(value);
    }
    if(typeof value!=='number' || !isFinite(value)) throw new Error('This control requires a finite number.');
    var integral=['java.lang.Integer','java.lang.Long','java.lang.Short','java.lang.Byte'];
    if(integral.indexOf(name)>=0 && Math.floor(value)!==value) throw new Error('This control requires an integer.');
    if(integral.indexOf(name)>=0 || name==='java.lang.Double' || name==='java.lang.Float') {
        return Java.type(name).valueOf(String(value));
    }
    throw new Error('Unsupported control value type: '+name);
}
function menuItem(path) {
    var bar=app.frmMain.getJMenuBar(), parent=bar, item=null;
    for(var n=0;n<path.length;n++) {
        var children=parent instanceof JMenu?parent.getMenuComponents():parent.getComponents();
        item=null;
        for(var i=0;i<children.length;i++) {
            if(children[i] instanceof AbstractButton && String(children[i].getText())===path[n]) {
                item=children[i];break;
            }
        }
        if(item===null) throw new Error('Menu item not found: '+path.slice(0,n+1).join(' > '));
        if(!item.isEnabled()) throw new Error('Menu item is disabled: '+path[n]);
        parent=item;
    }
    if(item===null || item instanceof JMenu) throw new Error('Supply a complete path to an actionable menu item.');
    return item;
}
function dispatch(method,p) {
    p=p||{};
    if(method==='status') {
        var s=status();
        if(p.operation_id) s.operation=operations[p.operation_id]||null;
        return s;
    }
    if(method==='inspect') return inspect(p);
    if(method==='model_summary') return modelSummary();
    if(method==='activate') return later(method,function(){
        app.frmMain.setState(JFrame.NORMAL);app.frmMain.toFront();app.frmMain.requestFocus();
        (p.files||[]).forEach(openFile);
    });
    if(method==='quit') return later(method,function(){
        app.frmMain.dispatchEvent(new (Java.type('java.awt.event.WindowEvent'))(app.frmMain,201));
    });
    if(method==='click') {
        var b=component(p.id);
        if(!(b instanceof AbstractButton)) throw new Error('Component is not a button or menu item.');
        if(!b.isEnabled()) throw new Error('Control is disabled.');
        return later(method,function(){if(!liveComponent(b)||!b.isEnabled())throw new Error('Control is no longer available.');b.doClick(0);});
    }
    if(method==='menu') {
        var menu=menuItem(p.path);
        return later(method,function(){if(!liveComponent(menu)||!menu.isEnabled())throw new Error('Menu is no longer available.');menu.doClick(0);});
    }
    if(method==='set_text') {
        var text=component(p.id);
        if(!(text instanceof JTextComponent) || !text.isEditable() || !text.isEnabled()) throw new Error('Text field is not editable.');
        return later(method,function(){
            if(!liveComponent(text)||!text.isEditable()||!text.isEnabled())throw new Error('Field is no longer editable.');
            if(p.commit) {
                var listeners=text.getFocusListeners();
                // AMUA snapshots the old value on focus gain. Merely requesting
                // focus posts a later event, too late for a synchronous commit.
                var gained=new FocusEvent(text,FocusEvent.FOCUS_GAINED);
                for(var f=0;f<listeners.length;f++) listeners[f].focusGained(gained);
                text.setText(String(p.text));
                var lost=new FocusEvent(text,FocusEvent.FOCUS_LOST);
                for(var f=0;f<listeners.length;f++) listeners[f].focusLost(lost);
            } else {text.requestFocusInWindow();text.setText(String(p.text));}
        });
    }
    if(method==='select') {
        var c=component(p.id);
        if(!c.isEnabled()) throw new Error('Control is disabled.');
        if(c instanceof JTabbedPane || c instanceof JComboBox || c instanceof JList) {
            if(typeof p.index!=='number') throw new Error('This control requires index.');
            return later(method,function(){c.setSelectedIndex(p.index);});
        }
        else if(c instanceof JTable) {
            if(typeof p.row!=='number') throw new Error('This table requires row.');
            if(p.row<0 || p.row>=c.getRowCount()) throw new Error('Row is out of range.');
            c.changeSelection(p.row,p.column||0,false,false);
        }
        else if(c instanceof JSpinner || c instanceof JSlider) {
            if(typeof p.value!=='number') throw new Error('This control requires value.');
            return later(method,function(){
                if(c instanceof JSpinner) c.setValue(typedValue(p.value,c.getValue().getClass()));
                else if(Math.floor(p.value)!==p.value) throw new Error('Slider requires an integer.');
                else c.setValue(p.value);
            });
        }
        else throw new Error('Unsupported selection control.');
        return describe(c);
    }
    if(method==='table') {
        var t=component(p.id);
        if(!(t instanceof JTable)) throw new Error('Expected a table.');
        var rows=[], start=Math.max(0,p.offset||0),end=Math.min(t.getRowCount(),start+Math.min(500,p.limit||100));
        for(var r=start;r<end;r++) {
            var row=[];for(var j=0;j<t.getColumnCount();j++) row.push(str(t.getValueAt(r,j)));rows.push(row);
        }
        return {table:describe(t),offset:start,rows:rows};
    }
    if(method==='set_cell') {
        var table=component(p.id);
        if(!(table instanceof JTable) || !table.isCellEditable(p.row,p.column)) throw new Error('Cell is not editable.');
        var existing=table.getValueAt(p.row,p.column);
        var expected=table.getColumnClass(p.column);
        if(String(expected.getName())==='java.lang.Object' && existing!==null) expected=existing.getClass();
        var converted=typedValue(p.value,expected);
        return later(method,function(){table.setValueAt(converted,p.row,p.column);return {updated:true};});
    }
    if(method==='new_model') {
        var item=field(app,p.type==='markov'?'mntmMarkovModel':'mntmDecisionTree');
        return later(method,function(){item.doClick(0);});
    }
    if(method==='open_model') return later(method,function(){openFile(p.path);});
    if(method==='save_model') {
        var model=currentModel(), target=p.path||str(model.filepath);
        if(!target) throw new Error('Supply a path for the new model.');
        var destination=new File(String(target)).getAbsoluteFile();
        if(!String(destination.getName()).toLowerCase().endsWith('.amua')) throw new Error('Save path must end with .amua.');
        if(!destination.getParentFile().isDirectory()) throw new Error('Destination directory does not exist.');
        if(destination.exists() && !p.overwrite) throw new Error('File exists. Set overwrite=true only when intended.');
        return later(method,function(){
            var oldName=model.name;
            try {
                model.name=String(destination.getName()).replace(/\.amua$/i,'');
                Java.type('base.AtomicModelSave').save(model,destination.toPath(),!!p.overwrite);
            } catch(e) {model.name=oldName;model.unsavedChanges=true;throw e;}
            model.filepath=String(destination.getAbsolutePath());model.unsavedChanges=false;
            app.recentFiles.updateList(model.filepath,model.type);
            app.setTabName(model.name,model.type);
            app.frmMain.setTitle('Amua (ReyJay) V 3.3.1 - Engine 0.3.6 - '+model.name+' ('+model.filepath+')');
        });
    }
    if(method==='validate_model') {
        var m=currentModel(), console=field(app,'console');
        return later(method,function(){
            var offset=String(console.textConsole.getText()).length;
            var valid=m.checkModel(console,true);
            var selected=m.type===1?field(m.panelMarkov,'curNode'):null;
            return {valid:!!valid,diagnostics:String(console.textConsole.getText()).slice(offset),
                scope:selected!==null && selected.type===1?'selected_chain':'whole_model'};
        });
    }
    if(method==='run_model') {
        currentModel();
        if(!app.btnRunModel.isEnabled()) throw new Error('Run model is disabled.');
        return later(method,function(){app.btnRunModel.doClick(0);});
    }
    if(method==='console') {
        var console=field(app,'console'),fields=console.getClass().getDeclaredFields();
        for(var i=0;i<fields.length;i++) {
            fields[i].setAccessible(true);var value=fields[i].get(console);
            if(value instanceof JTextComponent) {
                var all=String(value.getText()),limit=Math.min(100000,p.limit||30000);
                return {text:all.slice(-limit),truncated:all.length>limit};
            }
        }
        throw new Error('Console text component not found.');
    }
    if(method==='canvas_click') {
        var canvas=component(p.id);
        if(!canvas.isShowing() || p.x<0 || p.y<0 || p.x>=canvas.getWidth() || p.y>=canvas.getHeight()) throw new Error('Coordinates are outside the visible component.');
        return later(method,function(){
            canvas.requestFocusInWindow();
            var button=p.button===3?3:1, now=System.currentTimeMillis(), clicks=p.click_count||1;
            canvas.dispatchEvent(new MouseEvent(canvas,MouseEvent.MOUSE_PRESSED,now,0,p.x,p.y,clicks,button===3,button));
            canvas.dispatchEvent(new MouseEvent(canvas,MouseEvent.MOUSE_RELEASED,now,0,p.x,p.y,clicks,button===3,button));
            canvas.dispatchEvent(new MouseEvent(canvas,MouseEvent.MOUSE_CLICKED,now,0,p.x,p.y,clicks,button===3,button));
        });
    }
    if(method==='screenshot') {
        var win=p.window?component(p.window):app.frmMain;
        if(!(win instanceof Window) || !win.isVisible()) throw new Error('Expected a visible window.');
        var BufferedImage=Java.type('java.awt.image.BufferedImage');
        var image=new BufferedImage(win.getWidth(),win.getHeight(),BufferedImage.TYPE_INT_ARGB);
        var graphics=image.createGraphics();win.printAll(graphics);graphics.dispose();
        var path=Paths.get(support,'snapshot-'+String(UUID.randomUUID())+'.png');
        Java.type('javax.imageio.ImageIO').write(image,'png',path.toFile());
        return {path:String(path),width:image.getWidth(),height:image.getHeight()};
    }
    throw new Error('Unknown AMUA operation: '+method);
}
function tick() {
    var stream=Files.newDirectoryStream(bridge,'*.request.json');
    try {
        var iter=stream.iterator(),processed=0;
        while(iter.hasNext() && processed++<12) {
            var path=iter.next(), response=Paths.get(String(path).replace(/\.request\.json$/,'.response.json'));
            var req=null;
            try {
                if(Files.size(path)>1024*1024) throw new Error('Request too large.');
                req=readJSON(path);Files.deleteIfExists(path);
                var tokenFile=Paths.get(support,'bridge.token');
                if(Files.exists(tokenFile) && req.token!==String(new java.lang.String(Files.readAllBytes(tokenFile),UTF8))) throw new Error('Invalid bridge credentials.');
                if(req.deadline && req.deadline*1000<Date.now()) throw new Error('Request expired before execution.');
                if(req.instance && req.instance!==instance) throw new Error('App instance changed; retry after checking status.');
                if(req.method!=='activate'&&req.method!=='quit'&&!Java.type('v21.McpAccess').isEnabled()) throw new Error('MCP access is disabled in Amua. Enable MCP Access beside Help.');
                requestDeadline=req.deadline?req.deadline*1000:null;
                var result=dispatch(req.method,req.params);requestDeadline=null;
                if(req.id) writeJSON(response,{id:req.id,result:result});
            } catch(e) {
                requestDeadline=null;Files.deleteIfExists(path);
                if(req && req.id) writeJSON(response,{id:req.id,error:String(e)});
                else System.err.println('Bridge request failed: '+e);
            }
        }
    } finally {stream.close();}
    if(Date.now()-lastHeartbeat>1000) {
        writeJSON(Paths.get(support,'status.json'),status());lastHeartbeat=Date.now();
    }
}

EventQueue.invokeLater(function() {
    try {
        // The original main() performs an unbounded network update check on the
        // event thread. Construct the same main window without that startup check.
        var UIManager=Java.type('javax.swing.UIManager'), looks=UIManager.getInstalledLookAndFeels();
        for(var i=0;i<looks.length;i++) if(String(looks[i].getName())==='Nimbus') UIManager.setLookAndFeel(looks[i].getClassName());
        app=new (Java.type('gui.frmMain'))('0.3.6');
        var icon=Java.type('javax.imageio.ImageIO').read(new File(resources,'Amua.png'));
        app.frmMain.setIconImage(icon);
        try {
            var mac=Java.type('com.apple.eawt.Application').getApplication();
            mac.setDockIconImage(icon);
            mac.setOpenFileHandler(function(event){
                var files=event.getFiles();
                for(var f=0;f<files.size();f++) openFile(String(files.get(f).getAbsolutePath()));
            });
            mac.setQuitHandler(function(event,response){
                response.cancelQuit();
                app.frmMain.dispatchEvent(new (Java.type('java.awt.event.WindowEvent'))(app.frmMain,201));
            });
            mac.setAboutHandler(function(){field(app,'mntmAboutAmua').doClick(0);});
        } catch(e) {System.err.println('macOS application handlers: '+e);}
        Java.type('v21.WorkflowPanel').install(app);
        app.frmMain.setTitle('Amua (ReyJay) V 3.3.1 - Engine 0.3.6');
        app.frmMain.setVisible(true);
        app.frmMain.toFront();
        try {Java.type('com.apple.eawt.Application').getApplication().requestForeground(true);}
        catch(e) {System.err.println('macOS foreground request: '+e);}
        timer=new Timer(150,function(){try{tick();}catch(e){System.err.println(e.stack||e);}});
        timer.start();
        writeJSON(Paths.get(support,'status.json'),status());
        launchArguments.forEach(function(path){if(String(path).toLowerCase().endsWith('.amua')) openFile(String(path));});
        System.out.println('AMUA desktop ready '+new java.util.Date()+' instance='+instance);
    } catch(e) {
        System.err.println(e.stack||e);
        writeJSON(Paths.get(support,'status.json'),{running:false,ready:false,error:String(e),heartbeat_ms:Date.now()});
        System.exit(1);
    }
});
