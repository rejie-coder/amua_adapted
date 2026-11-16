import base.AmuaModel;
import base.ModelNode;
import base.RunReport;
import lang.Language;
import tree.TreeNode;
import markov.MarkovNode;
import java.io.File;
import java.util.ArrayList;
import javax.xml.bind.JAXBContext;

/** Uses the engine's existing cluster mode; no desktop or provider required. */
public class HeadlessEngineCheck {
    public static AmuaModel load(String path) throws Exception {
        AmuaModel m=(AmuaModel)JAXBContext.newInstance(AmuaModel.class).createUnmarshaller().unmarshal(new File(path));
        m.language=new Language();m.dimInfo.language=m.language;
        m.innateVariables=new ArrayList<>();
        if(m.variables==null)m.variables=new ArrayList<>();if(m.parameters==null)m.parameters=new ArrayList<>();if(m.tables==null)m.tables=new ArrayList<>();if(m.constraints==null)m.constraints=new ArrayList<>();if(m.subgroupNames==null)m.subgroupNames=new ArrayList<>();if(m.subgroupDefinitions==null)m.subgroupDefinitions=new ArrayList<>();
        for(main.Variable v:m.variables){v.value=new math.Numeric[1];v.locked=new boolean[1];v.dependents=new ArrayList<>();}
        m.cluster=true;m.numThreads=1;m.CRN=true;m.crnSeed=1234;
        if(m.type==0){
            m.tree.myModel=m;
            for(TreeNode n:m.tree.nodes){n.myModel=m;n.tree=m.tree;n.numDimensions=m.dimInfo.dimNames.length;}
        } else {
            m.addT();m.markov.myModel=m;m.markov.showTrace=false;
            for(MarkovNode n:m.markov.nodes){n.myModel=m;n.tree=m.markov;n.numDimensions=m.dimInfo.dimNames.length;}
            for(MarkovNode n:m.markov.nodes)if(n.type==1)chain(m,n,n);
        }
        return m;
    }
    static void chain(AmuaModel m, MarkovNode n, MarkovNode chain){
        n.chain=chain;
        for(int index:n.childIndices)chain(m,m.markov.nodes.get(index),chain);
    }
    public static void main(String[] args) throws Exception {
        for(String path:args)for(int simulation=0;simulation<2;simulation++){
            AmuaModel m=load(path);m.simType=simulation;m.cohortSize=simulation==1?5000:m.type==0?1:1000;
            ArrayList<String> errors=m.type==0?m.tree.parseTree():m.markov.parseTree();
            if(!errors.isEmpty())throw new AssertionError(errors.toString());
            RunReport report=new RunReport(m);
            if(m.type==0)m.tree.runModel(false,report);else m.markov.runModel(false,report,true);
            int strategies=m.getStrategies();
            for(int s=0;s<strategies;s++)System.out.println("RESULT "+m.type+" "+simulation+" "+m.strategyNames[s]+" "+m.getStrategyEV(s,0));
        }
        System.out.println("PASS headless original engine tree/Markov cohort and seeded Monte Carlo");
    }
}
