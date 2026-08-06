/**
 * END-TO-END CONSISTENCY: RESULT (microservice) vs the RENDERED TABLES (n8n node).
 *
 * Why this exists: four consecutive live runs were burned on the same class of defect — a consumer
 * number rendered from one leg while the verdict came from the other. The gate caught each one
 * AFTER the money was spent. This test runs the REAL analyze() output through the REAL Render
 * Tables node code and asserts the published rungs are identical, so the mismatch is caught here
 * instead of on a paid run.
 *
 * Generates its own fixture: python writes /tmp/ma_result.json from analyze() with an FCF-
 * conservative payload (the MA shape), then the node is executed against it.
 *
 * Run:  node tests/test_e2e_result_vs_tables.js
 */
const fs=require('fs'), path=require('path'), vm=require('vm');
const WFDIR=path.join(__dirname,'..','workflow');   // v4.2.54: no hardcoded absolute path — the archive unpacks anywhere
const wfFile=fs.readdirSync(WFDIR).filter(f=>f.endsWith('.json')).sort().pop();
const WF=JSON.parse(fs.readFileSync(path.join(WFDIR,wfFile),'utf8'));
const FIXTURE='/tmp/ma_result.json';
if(!fs.existsSync(FIXTURE)){
  require('child_process').execSync(
    "cd " + path.join(__dirname,'..') + " && python3 -c \"import sys,json;sys.path.insert(0,'microservice');sys.path.insert(0,'tests');import app;from test_harness import mature_data,mature_spec;d=mature_data();d['levered_fcf_per_share']=11.0;s=mature_spec();s['assumptions']['discount_rate']=0.12;print(json.dumps(app.analyze(d,s)))\" > " + FIXTURE,
    {shell:'/bin/bash'});
}
const RES=JSON.parse(fs.readFileSync(FIXTURE,'utf8'));
const rt=WF.nodes.find(n=>n.name==='Render Tables');
console.log('workflow:',wfFile);

(async()=>{
const item={json:{result:RES,ticker:'MA',chat_id:1}};
const ctx={console,JSON,Math,Number,String,Object,Array,Buffer,Date,
  $input:{all:()=>[item],first:()=>item},
  $:(name)=>{
    if(name==='Run Code') return {first:()=>({json:RES}),all:()=>[{json:RES}]};
    if(name==='Eligibility') return {first:()=>({json:{ticker:'MA',chat_id:1,category:'growth'}}),all:()=>[item]};
    return {first:()=>({json:{ticker:'MA',chat_id:1,spec:{},result:RES}}),all:()=>[item]};
  },
  $json:item.json};
ctx.global=ctx;
let out;
const fn=new Function('$','$input',`return (async () => { ${rt.parameters.jsCode} })();`);
try{ out=await fn(ctx.$,ctx.$input); }
catch(e){ console.log('ОШИБКА выполнения ноды:',e.message.slice(0,300)); process.exit(1); }
const md=(out&&out[0]&&out[0].json&&(out[0].json.tables_md||out[0].json.md))||JSON.stringify(out).slice(0,300);
// вытащить ступени из отрендеренной таблицы
const rungs=[...String(md).matchAll(/\|\s*(10|20|30)%\s*\|\s*\$?([0-9.]+)/g)].map(m=>[m[1],parseFloat(m[2])]);
console.log('\n=== ТАБЛИЦА (реальный рендер ноды) ===');
console.log('ступени в таблице:',rungs);
const legLine=String(md).match(/MoS ladder[^\n]*/);
console.log('заголовок ladder:',legLine?legLine[0]:'(не найден)');
const mosLine=String(md).match(/MoS \((GAAP|FCF\/sh)\)/);
console.log('ярлык MoS:',mosLine?mosLine[0]:'(не найден)');

console.log('\n=== СВЕРКА ===');
const want=RES.mos_ladder.map(x=>x.buy_threshold_price);
const got=rungs.map(r=>r[1]);
const ok=JSON.stringify(want)===JSON.stringify(got);
console.log('RESULT ступени:',want);
console.log('ТАБЛИЦА ступени:',got);
console.log(ok?'✅ СОВПАДАЮТ — расхождения мемо/RESULT быть не может':'❌ РАСХОЖДЕНИЕ — гейт снова поймает');
const legOk = String(md).includes('leg: '+RES.mos_ladder_leg);
const mosOk = String(md).includes(RES.dual_basis.verdict_leg==='fcf_per_share'?'MoS (FCF/sh)':'MoS (GAAP)');
console.log(legOk?'✅ заголовок ladder называет ногу':'❌ заголовок не называет ногу');
console.log(mosOk?'✅ ярлык MoS соответствует вердикт-ноге':'❌ ярлык MoS не той ноги');
process.exit((ok&&legOk&&mosOk)?0:1);
})();
