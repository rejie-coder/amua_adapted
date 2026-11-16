// Isolated comparison driver. Uses only the supplied AMUA classes for baseline.
var mode=String(arguments[0]), out=String(arguments[1]);
var System=Java.type('java.lang.System'), Files=Java.type('java.nio.file.Files'), Paths=Java.type('java.nio.file.Paths');
var EventQueue=Java.type('java.awt.EventQueue'), UTF8=Java.type('java.nio.charset.StandardCharsets').UTF_8;
Files.createDirectories(Paths.get(out));
var started=System.nanoTime();
function get(o,n){var f=o.getClass().getDeclaredField(n);f.setAccessible(true);return f.get(o);}
function set(o,n,v){var f=o.getClass().getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
function write(name,value){Files.write(Paths.get(out,name),new java.lang.String(JSON.stringify(value,null,2)).getBytes(UTF8));}
function arrays(a){return Java.from(a).map(Number);}
if(mode==='original') Java.type('main.Amua').main(Java.to([],'java.lang.String[]'));
else load(String(System.getProperty('amua.resources'))+'/bootstrap.js');
EventQueue.invokeLater(function(){
 try {
    var f=Java.type('gui.frmMain').class.getDeclaredField('main');f.setAccessible(true);
    var main=f.get(null), console=get(main,'console');
    var result={mode:mode,visible:main.frmMain.isShowing(),startup_ms:Number(System.nanoTime()-started)/1e6,cases:[]};
    function add(m,parent,type){var p=m.type===0?m.panelTree:m.panelMarkov;set(p,'curNode',parent);m.addNode(type);return get(p,'curNode');}
    function parameter(m,name,expression){var p=new (Java.type('main.Parameter'))();p.name=name;p.expression=expression;m.parameters.add(p);m.addParameter(p);}
    function fixture(type){
        get(main,type===0?'mntmDecisionTree':'mntmMarkovModel').doClick(0);
        var m=get(main,'curModel'),root=type===0?m.tree.nodes.get(0):m.markov.nodes.get(0);
        m.name=type===0?'decision-tree':'markov';parameter(m,'p','0.25');
        if(type===0){
            var a=add(m,root,1);a.name='Treatment';
            var a1=add(m,a,2);a1.name='Success';a1.prob='p';a1.payoff[0]='100';
            var a2=add(m,a,2);a2.name='Failure';a2.prob='C';a2.payoff[0]='20';
            var b=add(m,root,1);b.name='Control';
            var b1=add(m,b,2);b1.name='Success';b1.prob='0.5';b1.payoff[0]='50';
            var b2=add(m,b,2);b2.name='Failure';b2.prob='C';b2.payoff[0]='10';
        } else {
            ['Treatment','Control'].forEach(function(name,i){
                var chain=add(m,root,1);chain.name=name;chain.terminationCondition='t>=4';
                var well=add(m,chain,2);well.prob='1';well.rewards[0]=i===0?'10':'8';
                var dead=add(m,chain,2);dead.prob='0';dead.rewards[0]='0';
                var remain=add(m,well,4);remain.name='Remain';remain.prob=i===0?'1-p':'0.5';remain.transition=well.name;
                var die=add(m,well,4);die.name='Die';die.prob='C';die.transition=dead.name;
                var absorb=add(m,dead,4);absorb.name='Absorb';absorb.prob='1';absorb.transition=dead.name;
            });
            set(m.panelMarkov,'curNode',m.markov.nodes.get(0));m.markov.showTrace=false;
        }
        m.numThreads=1;m.CRN=true;m.crnSeed=1234;
        m.filepath=String(Paths.get(out,m.name+'.amua'));m.saveModel();return m;
    }
    function record(m,simulation){
        m.simType=simulation;m.cohortSize=simulation===1?5000:(m.type===0?1:1000);
        var valid=m.checkModel(console,true);
        if(!valid) throw new Error('Fixture rejected: '+console.textConsole.getText());
        m.runModel(console,true);
        var count=m.getStrategies(),values=[];
        for(var s=0;s<count;s++) values.push({strategy:String(m.strategyNames[s]),ev:m.getStrategyEV(s,0)});
        result.cases.push({model:m.type===0?'decision-tree':'markov',simulation:simulation===0?'cohort':'seeded_monte_carlo',values:values});
    }
    ['decision-tree','markov'].forEach(function(name,i){
        var m;
        if(mode==='original') {
            m=fixture(i);m.filepath=null;
            main.openModel(new java.io.File(String(Paths.get(out,name+'.amua'))));m=get(main,'curModel');
            m.filepath=String(Paths.get(out,'original-open-save-'+name+'.amua'));m.saveModel();
        }
        else {openFile(String(Paths.get(out,name+'.amua')));m=get(main,'curModel');}
        record(m,0);record(m,1);
        if(mode!=='original') {
            // Match the original validator on a setting parseModel does not check.
            var dim=m.dimInfo.objectiveDim;m.dimInfo.objectiveDim=99;
            var parsed=m.parseModel().size();var full=m.checkModel(console,true);
            if(parsed!==0 || full!==false) throw new Error('Invalid-outcome regression fixture failed');
            m.dimInfo.objectiveDim=dim;
            var d=new (Java.type('javax.swing.JDialog'))(main.frmMain,'Budget regression',false);
            d.setSize(200,100);d.setVisible(true);
            var truncated=inspect({max_nodes:1});
            if(!truncated.truncated) throw new Error('Inspection budget regression failed');d.dispose();
        }
    });
    result.console=String(console.textConsole.getText());
    write(mode+'-results.json',result);System.exit(0);
 } catch(e){write(mode+'-error.json',{error:String(e),stack:String(e.stack)});System.err.println(e.stack||e);System.exit(1);}
});
