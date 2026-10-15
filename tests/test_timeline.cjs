const assert=require('node:assert/strict');
const {model}=require('../web/timeline.js');
const report=findings=>({inventory:{start_ns:0,end_ns:100e9},findings});
const event=(start,end,stream='camera')=>({code:'BLACK_RUN',stream,start_s:start,end_s:end});
let result=model(report([event(20,25),event(20,25),event(22,26),event(50,51)]));
assert.equal(result.groups.length,1);
assert.equal(result.groups[0].items.length,3); // Duplicated clock evidence is displayed once.
assert.equal(result.groups[0].lanes.length,2); // Overlaps remain individually selectable.
assert.equal(result.groups[0].lanes[0][0].left,20);
assert.equal(result.groups[0].lanes[0][0].width,5);
result=model(report([event(0,0),event(-1,4),event(110,115),event(5,4)]));
assert.equal(result.groups.length,0);assert.equal(result.untimed.length,4);
result=model(report([event(99,120),event(100,100,'other')]));
assert.equal(result.groups[0].items[0].end,100);
assert.equal(result.groups[1].items[0].start,100);
assert.ok(result.groups[1].lanes[0][0].width>0);
assert.equal(model({findings:[event(2,3)]}).duration,null);
assert.equal(model({inventory:{start_ns:null,end_ns:100e9},findings:[]}).duration,null);
result=model(report([]),{status:'checked',streams:[{topic:'camera',runs:[{start_s:4,end_s:8}]}]});
assert.equal(result.groups[0].code,'POSSIBLE_OBSTRUCTION');assert.ok(result.obstructionChecked);
assert.equal(model(report([])).groups.length,0);
console.log('Timeline checks passed: positions, duplicates, overlaps, invalid times, clipping, point events, missing duration and obstruction.');
