/**
 * Resolves every identifier in every Code node (eslint no-undef).
 *
 * WHY THIS EXISTS, twice over:
 *  - v4.0.1: Render Tables referenced `gt` (ground truth is `el`) -> "gt is not defined" in prod.
 *  - v4.2:   removing `const TIINGO` left one live use in the pe_hist_median block. It PARSED
 *            fine (test_syntax.js green), threw ReferenceError at runtime, and the surrounding
 *            try/catch SWALLOWED it -> pe_hist_median silently null -> the PE cap lost its best
 *            anchor and nothing in the report said so. A silent null is worse than a crash.
 *
 * Parsing is not resolving. This check resolves.
 *
 * Requires: npm install eslint@8   (run from the repo root)
 * Run: node tests/test_undef.js
 */
const fs = require('fs');
const path = require('path');

let Linter;
try {
  ({ Linter } = require(process.env.ESLINT_PATH || 'eslint'));
} catch (e) {
  // Exit 2 ("could not run"), never 0. This block used to exit 0: on a fresh container with no
  // eslint it printed ONE dim stderr line — eaten by any `| tail` — and run_tests.py went on to
  // certify "ALL GREEN — safe to deploy" having resolved zero identifiers in zero nodes. The
  // gate that exists to catch `gt is not defined` was itself the thing not running.
  // This is the v4.2.2 lesson wearing a different hat: absence, spelled as success.
  console.error('  CANNOT RUN  eslint missing — the no-undef gate did NOT execute.');
  console.error('              fix: npm install        (from the repo root)');
  process.exit(2);
}

// Globals n8n injects into a Code node, plus standard runtime.
const N8N_GLOBALS = {
  $: 'readonly', $input: 'readonly', $json: 'readonly', $node: 'readonly',
  $items: 'readonly', $workflow: 'readonly', $execution: 'readonly',
  $now: 'readonly', $today: 'readonly', $runIndex: 'readonly', $prevNode: 'readonly',
  $parameter: 'readonly', $vars: 'readonly', $env: 'readonly',
  Buffer: 'readonly', console: 'readonly', require: 'readonly',
  process: 'readonly', DateTime: 'readonly', Interval: 'readonly', Duration: 'readonly',
};

// Coverage floor. If the JSON shape drifts (or someone points this at an empty dir), `total`
// silently falls to 0 and "0 of 0 resolve" would exit green — a suite that examined nothing,
// reporting success. A floor, not an exact count: adding nodes is fine, losing them is not.
const MIN_CODE_NODES = 19;

const linter = new Linter();
const wfDir = path.join(__dirname, '..', 'workflow');
let total = 0, failed = 0;

for (const file of fs.readdirSync(wfDir).filter(f => f.endsWith('.json'))) {
  const wf = JSON.parse(fs.readFileSync(path.join(wfDir, file), 'utf8'));
  for (const node of wf.nodes || []) {
    const code = node.parameters && node.parameters.jsCode;
    if (!code) continue;
    total++;
    // n8n wraps Code-node source in an async function, so top-level await/return are legal.
    const wrapped = `async function __n8nNode() {\n${code}\n}`;
    const messages = linter.verify(wrapped, {
      parserOptions: { ecmaVersion: 2022, sourceType: 'script' },
      env: { es2021: true, node: true },
      globals: N8N_GLOBALS,
      rules: { 'no-undef': 'error' },
    });
    const undef = messages.filter(m => m.ruleId === 'no-undef');
    if (undef.length) {
      failed++;
      console.error(`  FAIL  ${file} -> ${node.name}`);
      for (const m of undef) console.error(`        line ${m.line}: ${m.message}`);
    }
  }
}

if (total < MIN_CODE_NODES) {
  console.error(`  CANNOT RUN  harvested only ${total} code nodes, expected >= ${MIN_CODE_NODES}.`);
  console.error('              this gate did NOT cover the workflow — fix the harvester, do not lower the floor.');
  process.exit(2);
}

console.log(`undef: ${total - failed} of ${total} code nodes resolve, ${failed} failed`);
process.exit(failed ? 1 : 0);
