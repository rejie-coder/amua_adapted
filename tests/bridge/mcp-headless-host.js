var Files=Java.type('java.nio.file.Files'),Paths=Java.type('java.nio.file.Paths'),System=Java.type('java.lang.System'),UTF8=Java.type('java.nio.charset.StandardCharsets').UTF_8;
var profile=System.getProperty('amua.support'),resources=System.getProperty('amua.resources');Files.createDirectories(Paths.get(profile,'bridge'));
Files.write(Paths.get(profile,'bridge.token'),new java.lang.String('synthetic-bridge-token').getBytes(UTF8));
var src=String(new java.lang.String(Files.readAllBytes(Paths.get(resources,'bootstrap.js')),UTF8));var stop=src.lastIndexOf('\nEventQueue.invokeLater(function() {');load({script:src.substring(0,stop),name:'production-bridge.js'});
EventQueue.invokeAndWait(function(){
 app=Java.type('v21.McpHeadlessHost').create();var m=Java.type('HeadlessEngineCheck').load(System.getProperty('amua.fixture'));
 var models=app.getClass().getDeclaredField('modelList');models.setAccessible(true);models.get(app).add(m);
 var current=app.getClass().getDeclaredField('curModel');current.setAccessible(true);current.set(app,m);
 var text=new (Java.type('javax.swing.JTextField'))('before-synthetic');text.addNotify();var id=componentId(text);
 System.setProperty('amua.test.field.id',id);components[id]=text;
 Files.write(Paths.get(profile,'field-id.txt'),new java.lang.String(id).getBytes(UTF8));
 writeJSON(Paths.get(profile,'status.json'),status());
});
var deadline=Date.now()+90000;
while(Date.now()<deadline&&!Files.exists(Paths.get(profile,'stop'))){
 EventQueue.invokeAndWait(function(){tick();var id=System.getProperty('amua.test.field.id');Files.write(Paths.get(profile,'field-value.txt'),components[id].getText().getBytes(UTF8));});
 Java.type('java.lang.Thread').sleep(20);
}
System.exit(0);
