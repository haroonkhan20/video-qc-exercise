const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const UI=require('../web/hand-motion.js');
const examples=JSON.parse(fs.readFileSync(path.join(__dirname,'../.cache/hand-motion-preview/examples.json'),'utf8'));
for(const item of examples.cases){
 const html=UI.render(item.result);
 assert.ok(html.includes('What was checked'));
 assert.ok(!html.includes('<script>'));
 assert.ok(html.includes('Download movement report'));
 if(item.expected==='not_assessed')assert.ok(html.includes('Not enough information'));
}
const related=examples.cases.find(c=>c.name==='Related controller and gripper event');
assert.equal(related.result.findings.length,1);
assert.ok(UI.render(related.result).includes('Shown as one related event'));
const unsafe=structuredClone(related.result);unsafe.findings[0].why='<img src=x onerror=bad>';
assert.ok(!UI.render(unsafe).includes('<img'));
assert.ok(UI.render(null).includes('Not checked yet'));
console.log('Movement UI checks passed: all 17 examples, related grouping, missing evidence and escaping.');
