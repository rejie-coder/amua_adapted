var System=Java.type('java.lang.System'),EventQueue=Java.type('java.awt.EventQueue'),Timer=Java.type('javax.swing.Timer'),JFrame=Java.type('javax.swing.JFrame');
load(String(System.getProperty('amua.resources'))+'/bootstrap.js');
var sizes=[[1680,955],[1280,800]],result=[],index=0;
EventQueue.invokeLater(function(){field(app,'mntmDecisionTree').doClick(0);app.frmMain.setExtendedState(JFrame.NORMAL);next();});
function next(){if(index>=sizes.length){System.out.println(JSON.stringify({sizes:result}));System.exit(result.every(function(x){return x.canvas_width>=640&&x.canvas_height>=480;})?0:1);return;}
 var size=sizes[index];app.frmMain.setBounds(0,25,size[0],size[1]);app.frmMain.validate();
 var timer=new Timer(1100,function(){
  var viewport=currentModel().panelTree.getParent(),d=viewport.getExtentSize();result.push({width:size[0],height:size[1],canvas_width:d.width,canvas_height:d.height});
  var BufferedImage=Java.type('java.awt.image.BufferedImage'),image=new BufferedImage(app.frmMain.getWidth(),app.frmMain.getHeight(),BufferedImage.TYPE_INT_RGB),g=image.createGraphics();app.frmMain.paintAll(g);g.dispose();Java.type('javax.imageio.ImageIO').write(image,'png',new java.io.File(String(System.getProperty('amua.evidence'))+'/candidate-'+size[0]+'.png'));index++;next();
 });timer.setRepeats(false);timer.start();
}
