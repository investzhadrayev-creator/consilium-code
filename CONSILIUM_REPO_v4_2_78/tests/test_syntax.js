/**
 * Syntax-checks EVERY Code node in the workflow.
 *
 * v4.2: a patch spliced the Gather Data source by character offset and chopped 87 chars off
 * the head of the node. The workflow JSON stayed valid, every python test passed, and the
 * defect reached production as "SyntaxError: Unexpected token ')'" — a run that dies at the
 * first node with no report and no obvious cause. Nothing in the suite parsed node source.
 * Now everything does. Cheap, and it makes a whole class of edit-corruption impossible to ship.
 *
 * Run: node tests/test_syntax.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Coverage floor — see test_undef.js. "0 of 0 parse" must never exit green.
const MIN_CODE_NODES = 19;

const wfDir = path.join(__dirname, '..', 'workflow');
const files = fs.readdirSync(wfDir).filter(f => f.endsWith('.json'));
let total = 0, failed = 0;

for (const file of files) {
  const wf = JSON.parse(fs.readFileSync(path.join(wfDir, file), 'utf8'));
  for (const node of wf.nodes || []) {
    const code = node.parameters && node.parameters.jsCode;
    if (!code) continue;
    total++;
    // n8n wraps Code-node source in an async IIFE, so top-level await is legal there.
    const wrapped = `(async () => {\n${code}\n})();`;
    try {
      new vm.Script(wrapped, { filename: `${file}:${node.name}` });
    } catch (e) {
      failed++;
      console.error(`  FAIL  ${file} -> ${node.name}`);
      console.error(`        ${e.message}`);
    }
  }

  // Placeholders must be exactly the two known non-secrets — a stray one means a node was
  // edited without being finished.
  const blob = JSON.stringify((wf.nodes || []).filter(n => n.type !== 'n8n-nodes-base.stickyNote'));
  const found = [...new Set((blob.match(/YOUR_[A-Z_]+/g) || []))].sort();
  const allowed = ['YOUR_NAME', 'YOUR_PYTHON_SERVICE_URL', 'YOUR_TELEGRAM_CHAT_ID'];
  const unexpected = found.filter(p => !allowed.includes(p));
  if (unexpected.length) {
    failed++;
    console.error(`  FAIL  ${file}: unexpected placeholders ${JSON.stringify(unexpected)}`);
  }
}

if (total < MIN_CODE_NODES) {
  console.error(`  CANNOT RUN  harvested only ${total} code nodes, expected >= ${MIN_CODE_NODES}.`);
  console.error('              this gate did NOT cover the workflow — fix the harvester, do not lower the floor.');
  process.exit(2);
}

console.log(`syntax: ${total - failed} of ${total} code nodes parse, ${failed} failed`);
process.exit(failed ? 1 : 0);
