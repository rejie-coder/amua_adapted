// Candidate-engine expression tests. Absolute tolerance is predeclared 1e-10.
var Files=Java.type('java.nio.file.Files'),Paths=Java.type('java.nio.file.Paths'),System=Java.type('java.lang.System');
var Lang=Java.type('lang.Language'),Model=Java.type('base.AmuaModel'),ArrayList=Java.type('java.util.ArrayList');
var I=Java.type('math.Interpreter'),Numeric=Java.type('math.Numeric');
var language=new Lang(),model=new Model();model.language=language;model.parameters=new ArrayList();model.variables=new ArrayList();model.innateVariables=new ArrayList();model.tables=new ArrayList();model.constraints=new ArrayList();
var cases=[], failures=0;
function record(name,body){try{var value=body();cases.push({name:name,status:'pass',actual:value});}catch(e){failures++;cases.push({name:name,status:'fail',error:String(e)});}}
function near(a,b){if(!isFinite(a)||Math.abs(a-b)>1e-10)throw new Error('Expected '+b+'; actual '+a);return Number(a);}
function matrix(n){return n.getClass().getDeclaredField('matrix').get(n);}
function scalar(expr,expected){record(expr,function(){return near(I.evaluate(expr,model,false,language).getDouble(language),expected);});}
[
['2+3*4',14],['(2+3)^2',25],['abs(-7)',7],['sqrt(81)',9],['log(exp(2))',2],['log10(100)',2],['sin(0)+cos(0)',1],['choose(5,2)',10],['fact(5)',120],['if(3>2,7,9)',7],['mean(1,2,3)',2],['sum(1,2,3)',6],['product(2,3,4)',24],['min(min(4,1),7)',1],['max(max(4,1),7)',7],['logistic(0)',0.5],['bound(12,0,10)',10],
['det([[1,2],[3,4]])',-2],['tr([[1,2],[3,4]])',5],['nrow([[1,2],[3,4]])',2],['ncol([[1,2],[3,4]])',2],
['Bern(0.25,~)',0.25],['Bin(10,0.3,~)',3],['Pois(4,~)',4],['Norm(3,2,~)',3],['Beta(2,3,~)',0.4],['Gamma(2,3,~)',6],['Expo(2,~)',0.5],['Unif(2,6,~)',4],['Tri(0,2,4,~)',2],['TruncNorm(0,1,-1,1,~)',0]
].forEach(function(x){scalar(x[0],x[1]);});
record('matrix inverse multiplication',function(){var n=I.evaluate('[[1,2],[3,4]]*inv([[1,2],[3,4]])',model,false,language);near(matrix(n)[0][0],1);near(matrix(n)[0][1],0);near(matrix(n)[1][0],0);near(matrix(n)[1][1],1);return 'identity 2x2';});
record('Dirichlet mean vector',function(){var n=I.evaluate('Dir([2,3],~)',model,false,language);near(matrix(n)[0][0],.4);near(matrix(n)[0][1],.6);return [.4,.6];});
['sqrt(-1)','Bern(2,~)','det([1,2,3])','missing_symbol+1','1+'].forEach(function(expr){record('invalid rejected: '+expr,function(){var rejected=false;try{I.evaluate(expr,model,false,language);}catch(e){rejected=true;}if(!rejected)throw new Error('Invalid expression accepted');return 'rejected';});});
record('seeded distribution sampling repeats',function(){var R=Java.type('main.MersenneTwisterFast'),D=Java.type('math.Distributions');var first=new R(4321),second=new R(4321),params=Java.to([new Numeric(0.0),new Numeric(1.0)],'math.Numeric[]'),values=[];for(var i=0;i<20;i++){var a=D.sample('Norm',params,first,language).getDouble(language),b=D.sample('Norm',params,second,language).getDouble(language);near(a,b);values.push(a);}return values;});
record('six locale resource bundles preserve expression evaluation',function(){var Locale=Java.type('java.util.Locale'),all=['en','es','fr','km','pt','zh'];all.forEach(function(code){var l=new Lang();l.warnVersion=false;l.setLocale(new Locale(code));if(!l.base.containsKey('menu.run')||!l.message.containsKey('err.invalid_params'))throw new Error('Missing core resource '+code);near(I.evaluate('sqrt(81)+Beta(2,3,~)',model,false,l).getDouble(l),9.4);});return all;});
var result={suite:'candidate expression families',tolerance:'absolute 1e-10 fixed before execution; deterministic fixtures only',tests:cases.length,failures:failures,cases:cases};
Files.write(Paths.get(String(System.getProperty('test.output'))),new java.lang.String(JSON.stringify(result,null,2)).getBytes('UTF-8'));print(JSON.stringify({tests:cases.length,failures:failures}));System.exit(failures?1:0);
