/* Head evidence presentation. No detector logic and no fabricated measurements. */
const HeadMotionUI=(()=>{
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=value=>Number.isFinite(value)?Number(value).toLocaleString(undefined,{maximumFractionDigits:4}):'Unavailable';
 const labels={pass:'No issue found',review:'Needs review',fail:'Invalid data',not_assessed:'Not enough evidence',not_applicable:'No movement to compare',source_findings:'Original timing findings'};
 const categoryNames={values:'Missing or broken readings',rotation:'Direction readings',position:'Sudden movement',turns:'Sudden turns',timing:'Gaps and reading times',reference:'Tracking reference'};
 const names={HEAD_MISSING_STREAM:'Head readings are missing',HEAD_MISSING_FIELDS:'Missing position or rotation',HEAD_INVALID_VALUES:'Invalid position or rotation numbers',HEAD_ZERO_ROTATION:'Unusable rotation',HEAD_INVALID_TIMESTAMP:'Missing or invalid time',HEAD_ROTATION_SCALE:'Rotation needs checking',HEAD_POSITION_JUMP:'Sudden position change',HEAD_ROTATION_JUMP:'Sudden direction change',HEAD_FRAME_CHANGE:'Tracking reference changed',HEAD_FRAME_MISSING:'Tracking reference is missing',HEAD_TIME_ORDER:'Head times repeat or go backwards',HEAD_TIME_GAP:'Gap in head readings',HEAD_CHECK_UNAVAILABLE:'Head check could not complete',HEAD_MOTION_UNAVAILABLE:'Too few readings to compare movement'};
 function render(evidence,canAnalyze=false){
  let html='<section class="head-motion"><h2>Head movement</h2>';
  if(!evidence)return html+'<p>Not checked yet.</p><button id="checkHead"'+(canAnalyze?'':' disabled')+'>Check head movement</button><p id="headStatus" role="status">'+(canAnalyze?'Checks only this recording.':'Scanning is disabled pending deployment approval.')+'</p></section>';
  const metrics=evidence.metrics||{},settings=evidence.settings||{};
  html+='<div class="head-summary"><strong>'+esc(labels[evidence.severity]||'Not enough evidence')+'</strong><span>'+number(evidence.decoded_messages)+' / '+number(evidence.expected_messages??evidence.messages)+' readings read</span></div>';
  if(evidence.severity==='review')html+='<p class="attention-note">This movement needs a look. It may be normal. This warning limits the Overall Score to 8/10.</p>';
  if(evidence.severity==='fail')html+='<p class="attention-note">Some head readings are missing or unusable. Broken readings limit the score to 4/10; a missing head stream limits it to 2/10. A complete score may be unavailable.</p>';
  html+='<details class="technical"><summary>What was checked</summary><div class="head-categories">'+(evidence.categories||[]).map(category=>'<article><h3>'+esc(categoryNames[category.id]||category.name)+'</h3><strong class="head-state '+esc(category.state)+'">'+esc(labels[category.state]||'Not enough evidence')+'</strong><p>'+esc(reason(category,evidence))+'</p></article>').join('')+'</div>';
  html+='<dl class="head-metrics"><div><dt>Largest position step</dt><dd>'+number(metrics.largest_position_step)+' coordinate units</dd></div><div><dt>Largest direction change</dt><dd>'+number(metrics.largest_rotation_step_degrees)+'° between nearby readings</dd></div><div><dt>Rotation scaling difference</dt><dd>'+number(metrics.largest_rotation_norm_error)+' (allowance '+number(settings.rotation_norm_tolerance)+')</dd></div></dl>';
  if(metrics.position_min_xyz)html+='<details class="technical"><summary>Technical measurements</summary><p>X: '+number(metrics.position_min_xyz[0])+' to '+number(metrics.position_max_xyz[0])+'<br>Y: '+number(metrics.position_min_xyz[1])+' to '+number(metrics.position_max_xyz[1])+'<br>Z: '+number(metrics.position_min_xyz[2])+' to '+number(metrics.position_max_xyz[2])+'</p><pre>'+esc(JSON.stringify(settings,null,2))+'</pre></details>';
  html+='<p>Reference: <strong>'+esc((evidence.frame_ids||[]).join(', ')||'Unavailable')+'</strong>. Position units have not been confirmed; they are shown as coordinate units, not metres.</p>';
  html+='</details>';
  const findings=(evidence.findings||[]).filter(f=>f.severity!=='source_policy');
  html+=(findings.length?'<h3>Issues ('+findings.length+')</h3>':'')+(findings.length?findings.map(f=>'<article class="head-finding"><strong>'+esc(names[f.code]||f.code)+'</strong><p>'+esc(f.why)+'</p><p>'+ (Number.isFinite(f.start_s)&&Number.isFinite(f.end_s)?number(f.start_s)+'–'+number(f.end_s)+' seconds into the recording':'No exact time available')+'</p>'+contextButton(f)+'<details class="technical"><summary>Details</summary>'+measurement(f)+'<pre>'+esc(JSON.stringify(f,null,2))+'</pre></details></article>').join(''):'');
  html+=(canAnalyze?'<button id="checkHead">Recheck head movement</button>':'')+'<p id="headStatus" role="status"></p><a id="headDownload" class="download">Download head report</a></section>';
  return html;
 }
 function reason(category,evidence){
  if(category.state==='not_assessed')return 'There is not enough usable evidence for this check. No healthy result is inferred.';
  if(category.state==='not_applicable')return 'The head stayed still. Stillness can be normal.';
  if(category.state==='source_findings')return 'Existing timing or coverage findings remain in the original report and timeline.';
  const finding=(evidence.findings||[]).find(f=>f.category===category.id);
  if(finding)return finding.why;
  return ({values:'Position and direction readings are present and usable.',rotation:'Direction readings have the expected format.',position:'No unusually large movement was found compared with recent movement.',turns:'No turn exceeded the chosen limit: 45° within 0.1 seconds.',timing:'No head timestamp gap or ordering warning was found.',reference:'The tracking reference stayed the same.'})[category.id];
 }
 function measurement(f){
  const m=f.metrics||{};
  if(f.code==='HEAD_POSITION_JUMP')return '<p>Measured step: '+number(m.step_coordinate_units)+' coordinate units; '+number(m.multiple)+' times the recent typical step. Review threshold: '+number(m.allowed_multiple)+' times.</p>';
  if(f.code==='HEAD_ROTATION_JUMP')return '<p>Measured turn: '+number(m.angle_degrees)+'° in '+number(m.interval_seconds)+' seconds. Review threshold: '+number(m.allowed_degrees)+'°.</p>';
  if(f.code==='HEAD_ROTATION_SCALE')return '<p>Rotation magnitude: '+number(m.magnitude)+'; expected near 1. Difference: '+number(m.error)+'; allowance: '+number(m.allowed_error)+'.</p>';
  if(f.code==='HEAD_TIME_GAP')return '<p>Measured gap: '+number(m.gap_seconds)+' seconds. Allowance: '+number(m.allowed_seconds)+' seconds.</p>';
  return '';
 }
 function contextButton(f){
  if(!Number.isFinite(f.start_s)||!Number.isFinite(f.end_s)||f.start_s<0||f.end_s<f.start_s)return '';
  return '<button class="show-problem" data-problem-topic="'+esc(f.stream)+'" data-problem-start="'+f.start_s+'" data-problem-end="'+f.end_s+'">Show related camera images ↗</button><p>Camera images provide context; they do not prove a movement-data error.</p>';
 }
 return {render,names};
})();
if(typeof module!=='undefined')module.exports=HeadMotionUI;
