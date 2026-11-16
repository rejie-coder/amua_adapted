var System=Java.type('java.lang.System'),EventQueue=Java.type('java.awt.EventQueue');
load(String(System.getProperty('amua.resources'))+'/bootstrap.js');
EventQueue.invokeLater(function(){
 try{
  field(app,'mntmDecisionTree').doClick(0);
  var committed=false, queued=later('set_text',function(){committed=true;});
  field(app,'mntmDecisionTree').doClick(0);
  requestDeadline=Date.now()-1;var expired=later('save_model',function(){throw new Error('expired action executed');});requestDeadline=null;
  var button=new (Java.type('javax.swing.JButton'))('Disposable');button.addNotify();var id=componentId(button);var stale=dispatch('click',{id:id});button.removeNotify();
  EventQueue.invokeLater(function(){try{
   if(committed||operations[queued.operation_id].state!=='error')throw new Error('Wrong-model queued action accepted');
   if(operations[expired.operation_id].state!=='error')throw new Error('Expired queued action accepted');
   if(operations[stale.operation_id].state!=='error')throw new Error('Disposed control accepted');
   for(var i=0;i<32;i++)later('set_text',function(){});
   var rejected=false;try{later('set_text',function(){});}catch(e){rejected=String(e).indexOf('queue is full')>=0;}
   if(!rejected)throw new Error('Queue overflow accepted');
   System.out.println('PASS deferred wrong-model, expiry, disposed-control and queue-budget guards');System.exit(0);
  }catch(e){System.err.println(e.stack||e);System.exit(1);}});
 }catch(e){System.err.println(e.stack||e);System.exit(1);}
});
