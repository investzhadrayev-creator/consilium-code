/**
 * Executes the "Number Audit" node (v3.9) against a mock memo + RESULT.
 * The node is the deterministic anti-hallucination layer: every material number in the memo
 * must have a counterpart in RESULT/GROUND_TRUTH/tables. Python finds, the auditor judges.
 * Run: node tests/test_number_audit.js
 */
const fs = require('fs');
const path = require('path');
const wfDir = path.join(__dirname, '..', 'workflow');
const wfFile = fs.readdirSync(wfDir).filter(f=>f.startsWith('consilium_spine_v')&&f.endsWith('.json'))
  .sort((a,b)=>{const v=s=>s.replace('consilium_spine_v','').replace('.json','').split('_').map(Number);
    const[av,bv]=[v(a),v(b)];return(av[0]-bv[0])||((av[1]||0)-(bv[1]||0));}).pop();
const wf = JSON.parse(fs.readFileSync(path.join(wfDir, wfFile),'utf8'));
const node = wf.nodes.find(n=>n.name==='Number Audit');
if(!node){console.error('FAIL: Number Audit node not found in '+wfFile);process.exit(1);}

const RESULT = { pwfv: 320.69, ivc_base:{intrinsic_value:292.67, implied_cagr_pct:15.20},
  gps:{total:52}, dual_basis:{gaap_eps:{iv:325.19}} };
const ELIG = { ticker:'ADBE', levered_fcf:9.85e9, sbc_to_revenue:0.082, pe_hist_median:41.50 };
const TABLES = '| TOTAL GPS | 52 | MoS 30% threshold $225.14 |';
const MEMO = [
  'The base case values ADBE at $292.67 with implied CAGR of 15.20%.',          // sourced
  'Levered FCF is $9.85B and SBC runs at 8.2% of revenue.',                     // B/% scaling
  'Management guided FY26 EPS to $6.05.',                                       // NOT in sources -> unmatched
  'Competitor pricing pressure could cut ARPU by 47.3% in a downside.',         // invented -> unmatched
  'Consensus target is $497 [UNVERIFIED] pending data.',                        // marked -> skipped
  'Section 6.1 covers the radar and FY2026 timing.',                            // ordinal+year -> skipped
].join(' ');

function $(name){ return { first: () => ({ json:
  name==='Run Code' ? RESULT :
  name==='Eligibility' ? ELIG :
  name==='Render Tables' ? {tables_md:TABLES} :
  name==='Extract Memo' ? {memo_text:MEMO} : {} })}; }
const $input={first:()=>({json:{}})};

(async()=>{
  let res;
  try { res=(await eval(`(async()=>{ ${node.parameters.jsCode} })()`))[0].json; }
  catch(e){ console.error('FAIL: node threw:\n'+(e.stack||e.message)); process.exit(1); }
  let pass=0; const fails=[];
  const chk=(name,cond,msg)=>{ if(cond){pass++;} else fails.push(name+': '+msg); };
  const vals = res.unmatched.map(u=>u.value);
  chk('sourced numbers matched', !vals.includes('$292.67') && !vals.includes('15.20%'),
      'sourced number flagged: '+JSON.stringify(vals));
  chk('B/% scaling matched', !vals.includes('$9.85B') && !vals.includes('8.2%'),
      'scaled variants flagged: '+JSON.stringify(vals));
  chk('unsourced guidance flagged', vals.some(v=>v.includes('6.05')),
      'missed $6.05: '+JSON.stringify(vals));
  chk('invented percent flagged', vals.some(v=>v.includes('47.3')),
      'missed 47.3%: '+JSON.stringify(vals));
  chk('[UNVERIFIED] sentence skipped', !vals.some(v=>v.includes('497')),
      '497 from UNVERIFIED sentence flagged');
  chk('years and ordinals skipped', !vals.some(v=>v.includes('2026')||v==='6.1'),
      'year/ordinal flagged: '+JSON.stringify(vals));
  console.log('number_audit: '+pass+' passed, '+fails.length+' failed');
  fails.forEach(f=>console.error('  FAIL: '+f));
  process.exit(fails.length?1:0);
})();
