const $=id=>document.getElementById(id);
let records=[],filter='all',profiles=[],activeProfile='balanced-v1',selectedDigest=null,loadSequence=0,detailSequence=0;
const labels={pass:'Passed checks',fail:'Issues found',needs_review:'Needs a look',pending:'Waiting for results'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const size=n=>n>=1e9?(n/1e9).toFixed(2)+' GB':(n/1e6).toFixed(1)+' MB';
const badge=v=>'<span class="badge '+(labels[v]?v:'pending')+'">'+(labels[v]||'Pending')+'</span>';
const gradeLabels={acceptable:'Meets this standard',review:'Check before use',unacceptable:'Below this standard',not_assessed:'Not enough information'};
const marks=v=>v==null?'Not enough information':Number(v).toFixed(2)+'/10';
const gradeBadge=g=>g?'<strong class="grade-mark">'+marks(g.score)+'</strong><small class="grade-state '+g.recommendation+'">'+gradeLabels[g.recommendation]+'</small>':'<span class="grade-state">Pending</span>';
const names=Friendly.areas;
let editorBase=null;
async function api(url,opts){const r=await fetch(url,opts),d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function render(){
 const base=records.filter(r=>$('collection').value==='all'||r.dataset==='mentor');
 $('total').textContent=base.length;
 for(const [id,v] of [['passes','pass'],['fails','fail'],['reviews','needs_review']])$(id).textContent=base.filter(r=>r.verdict===v).length;
 const search=$('search').value.toLowerCase(),rows=base.filter(r=>(filter==='all'||(r.verdict||'pending')===filter)&&($('gradeFilter').value==='all'||(r.grading?.recommendation||'not_assessed')===$('gradeFilter').value)&&(r.name+r.digest+(r.aliases||[]).join(' ')).toLowerCase().includes(search));
 $('count').textContent=rows.length;
 $('rows').innerHTML=rows.length?rows.map(r=>'<tr><td><strong>'+esc(r.name)+'</strong><small>File ID · '+r.digest.slice(0,16)+'…</small></td><td>'+badge(r.verdict)+'</td><td title="'+esc(r.grading?'Score based on '+(profiles.find(p=>p.id===activeProfile)?.name||'your standard'):'Waiting for a result')+'">'+gradeBadge(r.grading)+'</td><td>'+esc((r.reason_codes||[]).map(c=>Friendly.issues[c]||'An issue needs attention').join(', ')||(r.verdict?'No issue found':r.workflow_state||'Awaiting result'))+'</td><td>'+size(r.bytes)+'</td><td>'+(r.verdict?'<button class="inspect" data-digest="'+r.digest+'">Inspect ↗</button>':esc(r.workflow_state||'Pending result'))+'</td></tr>').join(''):'<tr><td colspan="6">No recordings match this view.</td></tr>';
}
async function refresh(){
 const sequence=++loadSequence,profile=activeProfile;$('refresh').disabled=true;
 try{const d=await api('/api/recordings?profile='+encodeURIComponent(profile));if(sequence!==loadSequence)return;records=d.recordings;render();$('updated').textContent='Updated · '+new Date(d.updated_at*1000).toLocaleTimeString();}catch(e){if(sequence===loadSequence)$('notice').textContent='We could not load the results. Start the local services, then choose Refresh.';}finally{if(sequence===loadSequence)$('refresh').disabled=false;}
}
function gradingPanel(g){
 const losses=g.categories.filter(c=>c.score!=null&&c.score<10).sort((a,b)=>(10-b.score)*b.weight-(10-a.score)*a.weight);
 const why=g.score==null?'Some checks could not provide enough information, so a reliable overall score is not available.':g.critical_cap?'A serious file or data issue limits the score to 4, even if other areas look good.':losses.length?names[losses[0].id]+' lowered the score most. '+Friendly.category(losses[0]):'All checked areas met this standard without a score reduction.';
 return '<section class="grade-panel"><div class="grade-heading"><div><div class="eyebrow">YOUR STANDARD · '+esc(g.profile.id==='balanced-v1'?'Default':g.profile.name)+'</div><strong class="overall-grade">'+marks(g.score)+'</strong><span>'+gradeLabels[g.recommendation]+'</span></div></div><h3>Why this score?</h3><p>'+esc(why)+'</p>'+
 (g.original_verdict!=='pass'?'<p class="attention-note">The automatic checks found something that needs attention. A high score does not clear those issues; review the flagged moments below.</p>':'')+
 (g.critical_cap?'<p class="cap">Serious issue: '+esc(g.critical_cap.reasons.map(c=>Friendly.issues[c]||'Unusable recording data').join(', '))+'</p>':'')+
 '<p class="grade-scope">10 means this standard found no reason to lower the score. Open an area below to see what affected its mark.</p>'+
 g.categories.map(c=>'<details class="category"><summary><span>'+esc(names[c.id])+'</span><strong>'+marks(c.score)+'</strong><small>'+c.weight+'% of the final score</small></summary><p>'+esc(Friendly.category(c))+'</p><p class="help-text">'+(c.contribution==null?'This area needs more information.':'This area adds '+Number(c.contribution).toFixed(2)+' points to the total out of 10.')+(c.worst_stream?' Lowest measured mark: '+esc(Friendly.stream(c.worst_stream))+'.':'')+'</p>'+
 c.streams.map(t=>'<details class="stream-grade"><summary>'+esc(Friendly.stream(t.topic))+' · '+marks(t.score)+'</summary><div class="table-wrap"><table><thead><tr><th>WHAT WE CHECKED</th><th>MARK</th><th>WHY</th></tr></thead><tbody>'+t.parameters.map(p=>'<tr><td>'+esc(Friendly.parameter(p))+'</td><td>'+(!p.applicable?'Does not apply':marks(p.score))+'</td><td>'+esc(Friendly.why(p))+'</td></tr>').join('')+'</tbody></table></div><details class="technical"><summary>Technical details</summary><pre>'+esc(JSON.stringify(t,null,2))+'</pre></details></details>').join('')+'</details>').join('')+
 '<a class="download" id="gradeDownload">Download score report</a><details class="technical"><summary>Calculation and version details</summary><p>Calculated total before any serious-issue limit: '+(g.weighted_average==null?'not available':Number(g.weighted_average).toFixed(4)+'/10')+'</p><p class="mono">Standard version: '+esc(g.profile_version)+'<br>Grading engine: '+esc(g.engine_version)+'<br>Report ID: '+esc(g.source_report_hash)+'</p></details></section>';
}
const descriptions={BLACK_RUN:'Images stayed very dark. Inspect the scene to understand why.',BRIGHT_RUN:'Images stayed very bright. Check whether the scene explains this.',SENSOR_FLATLINE:'The sensor value stayed unchanged. A stationary gripper can be legitimate.',FROZEN_RUN:'Images changed very little. Check whether the scene was stationary.',BLUR_RUN:'Low image sharpness was detected. Inspect the scene and focus.',GAP_RUN:'A long interval between recorded messages was detected.',COVERAGE_MISMATCH:'A stream started late or ended early beyond the allowed boundary.',CHECK_UNAVAILABLE:'A required check could not finish. This is not evidence of healthy data.'};
async function detail(digest){
 selectedDigest=digest;const sequence=++detailSequence;
 const selected=records.find(r=>r.digest===digest);$('detailTitle').textContent=selected?.name||digest.slice(0,12);$('detailBody').textContent='Loading report and grade…';if(!$('detail').open)$('detail').showModal();
 try{
 const [r,g]=await Promise.all([api('/api/reports/'+digest),api('/api/grades/'+digest+'?profile='+encodeURIComponent(activeProfile))]);if(sequence!==detailSequence)return;
 $('detailBody').innerHTML='<p>Automatic check result: '+badge(r.verdict)+'</p>'+gradingPanel(g)+ '<h2>What needs attention ('+r.findings.length+')</h2>'+
 (r.findings.length?r.findings.map(f=>'<article class="finding"><strong>'+esc(Friendly.issues[f.code]||'An issue needs attention')+'</strong><p>'+esc(descriptions[f.code]||'This check found a problem. See the affected moments and optional technical details.')+'</p><p>'+esc(Friendly.stream(f.stream))+'</p><p>'+(f.start_s!=null?Number(f.start_s).toFixed(2)+'–'+Number(f.end_s).toFixed(2)+' seconds into the recording':'Applies to the whole recording')+'</p><details class="technical"><summary>Technical details</summary><pre>'+esc(JSON.stringify(f,null,2))+'</pre></details></article>').join(''):'<p>The automatic checks did not find an issue under their current rules.</p>')+
  '<section class="samples"><h2>Look at the recording</h2><p>These are saved snapshots, about one per second. The time below each picture is when it was taken.</p><div class="sample-controls"><label>Seconds into recording <input id="sampleTime" type="number" min="0" max="86400" step="0.1" value="0"></label><button id="loadSamples">Show images</button></div><div id="sampleGrid"></div></section><details class="technical"><summary>Detailed camera and sensor measurements</summary><div class="table-wrap"><table><thead><tr><th>CAMERA OR SENSOR</th><th>READINGS</th><th>READINGS / SECOND</th><th>PLAYBACK ERRORS</th><th>EST. MISSING READINGS</th></tr></thead><tbody>'+r.streams.map(s=>'<tr><td>'+esc(Friendly.stream(s.topic))+'</td><td>'+esc(s.timing?.log?.messages??'—')+'</td><td>'+(s.timing?.log?.effective_hz==null?'—':Number(s.timing.log.effective_hz).toFixed(2))+'</td><td>'+esc(s.stats?.video_decode_errors??'—')+'</td><td>'+esc(s.timing?.log?.estimated_dropped_frames??'—')+'</td></tr>').join('')+'</tbody></table></div></details><a class="download" id="download">Download original check report</a><details class="technical"><summary>File and processing details</summary><p class="mono">Recording: '+esc(r.digest)+'<br>Rules: '+esc(r.config_version)+'<br>Software: '+esc(r.code_version)+'</p></details>';
 const initial=r.findings.find(f=>f.start_s!=null);
 $('sampleTime').value=initial?((initial.start_s+initial.end_s)/2).toFixed(2):0;
 $('loadSamples').onclick=async()=>{
  const t=Number($('sampleTime').value);if(!Number.isFinite(t)||t<0||t>86400)return;
  $('loadSamples').disabled=true;$('sampleGrid').textContent='Loading camera samples…';
  try{const frames=await api('/api/samples/'+digest+'/'+t.toFixed(3));$('sampleGrid').innerHTML=frames.length?frames.map(f=>'<figure><img alt="'+esc(Friendly.stream(f.topic))+' at '+Number(f.seconds).toFixed(2)+' seconds" src="data:image/jpeg;base64,'+f.image+'"><figcaption>'+esc(Friendly.stream(f.topic))+'<br>'+Number(f.seconds).toFixed(2)+' seconds</figcaption></figure>').join(''):'No camera samples available for this recording.';}catch(e){$('sampleGrid').textContent=e.message;}finally{$('loadSamples').disabled=false;}
 };
 for(const [id,data,suffix] of [['download',r,'.json'],['gradeDownload',g,'.grade.json']]){const link=$(id);link.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));link.download=(selected?.name||digest+'.mcap').replace(/\.mcap$/,suffix);}
 }catch(e){$('detailBody').textContent=e.message;}
}
$('close').onclick=()=>$('detail').close();
$('rows').onclick=e=>{const b=e.target.closest('[data-digest]');if(b)detail(b.dataset.digest);};
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('selected',x===b));render();});
$('search').oninput=render;$('collection').onchange=render;$('refresh').onclick=refresh;
$('gradeFilter').onchange=render;
function chooseProfile(id){activeProfile=id;$('profile').value=id;$('standardHelp').textContent=id==='balanced-v1'?'Default is a balanced starting point. You can use it without changing any settings.':'Using your saved standard. Choose Use default to return to the balanced starting point.';refresh();if($('detail').open&&selectedDigest)detail(selectedDigest);}
$('profile').onchange=()=>chooseProfile($('profile').value);
$('useDefault').onclick=()=>chooseProfile('balanced-v1');
function profileOptions(){ $('standardHelp').textContent=activeProfile==='balanced-v1'?'Default is a balanced starting point. You can use it without changing any settings.':'Using your saved standard. Choose Use default to return to the balanced starting point.'; $('profile').innerHTML=profiles.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.id==='balanced-v1'?'Default — recommended':p.name)+'</option>').join('');$('profile').value=activeProfile; }
const limitSettings={
 rate_relative_tolerance:['Allowed change in recording speed (%)',100,'For example, 30 allows a 30% difference from the expected speed.'],
 payload_stamp_tolerance_ms:['Allowed disagreement between recorded times (seconds)',0.001,'How far the time inside a reading may differ from its saved time.'],
 coverage_start_tolerance_seconds:['Allowed missing time at the beginning (seconds)',1,'How late a camera or sensor may start compared with the others.'],
 coverage_end_tolerance_seconds:['Allowed missing time at the end (seconds)',1,'How early a camera or sensor may stop compared with the others.'],
 camera_sync_skew_ms:['Allowed difference between camera times (seconds)',0.001,'How far apart cameras may be when recording the same moment.'],
 camera_sync_drift_ms:['Allowed change in camera alignment (seconds)',0.001,'How much the difference between camera times may change over a recording.']
};
const weightChoices={
 balanced:{integrity:10,inventory:10,decoding:20,timing:20,alignment:15,image:20,sensor:5},
 image:{integrity:5,inventory:5,decoding:15,timing:20,alignment:3,image:50,sensor:2},
 timing:{integrity:5,inventory:5,decoding:15,timing:40,alignment:20,image:10,sensor:5}
};
const scoreChoices={balanced:{acceptable:8,review:5},strict:{acceptable:9,review:7},relaxed:{acceptable:7,review:4}};
function simpleSummary(){
 const a=Number($('acceptableCutoff').value),r=Number($('reviewCutoff').value);
 const priority=$('priority').value;
 $('simpleSummary').textContent=(priority==='image'?'Picture quality has the most influence. ':priority==='timing'?'Interruptions and recording alignment have the most influence. ':priority==='balanced'?'All areas share a balanced importance. ':'Your detailed choices set how much each area matters. ')+
 'Scores of '+a+'/10 or higher meet the standard; '+r+' to below '+a+' need a check before use. Lower scores are below the standard. Serious issues and missing information are always highlighted.';
}
function fillEditor(p,resetName=true){
 editorBase=JSON.parse(JSON.stringify(p));delete editorBase.version;
 if(resetName)$('profileName').value=p.id==='balanced-v1'?'My standard':p.name+' copy';
 $('acceptableCutoff').value=p.cutoffs.acceptable;$('reviewCutoff').value=p.cutoffs.review;$('flatlineAdvisory').checked=p.flatline_advisory;$('profileError').textContent='';
 $('priority').value=Object.keys(weightChoices).find(k=>Object.keys(names).every(n=>p.weights[n]===weightChoices[k][n]))||'custom';
 $('strictness').value=Object.keys(scoreChoices).find(k=>p.cutoffs.acceptable===scoreChoices[k].acceptable&&p.cutoffs.review===scoreChoices[k].review)||'custom';
 $('weightFields').innerHTML=Object.entries(p.weights).map(([k,v])=>'<label>'+names[k]+' (%) <input data-weight="'+k+'" type="number" min="0" max="100" step="0.1" value="'+v+'" required></label>').join('');
 $('limitFields').innerHTML=Object.entries(p.limits).map(([k,v])=>{const [label,scale,help]=limitSettings[k];return '<label>'+label+' <input data-limit="'+k+'" aria-label="'+label+'" type="number" min="0.000001" max="'+86400*scale+'" step="any" value="'+Number((v*scale).toPrecision(12))+'" required><small class="help-text">'+help+'</small></label>';}).join('');
 $('fractionFields').innerHTML=p.fraction_bands.map((b,i)=>'<div><label>Problem affects at most this much (%) <input data-fraction-max="'+i+'" type="number" min="0" max="100" step="any" value="'+b.max*100+'" '+(i===0||i===p.fraction_bands.length-1?'readonly':'')+' required></label><label>Give this mark out of 10 <input data-fraction-score="'+i+'" type="number" min="0" max="10" step="0.1" value="'+b.score+'" '+(i===0||i===p.fraction_bands.length-1?'readonly':'')+' required></label></div>').join('');
 $('limitBandFields').innerHTML=p.limit_bands.map((b,i)=>'<div><label>Measurement is up to this many times its allowance <input data-band-max="'+i+'" type="number" min="1" step="any" value="'+b.max+'" '+(i===0?'readonly':'')+' required></label><label>Give this mark out of 10 <input data-band-score="'+i+'" type="number" min="0" max="10" step="0.1" value="'+b.score+'" '+(i===0?'readonly':'')+' required></label></div>').join('');
 updateWeightTotal();simpleSummary();
}
$('customize').onclick=()=>{const p=profiles.find(x=>x.id===activeProfile);if(!p)return;fillEditor(p);$('advancedSettings').open=false;$('profileEditor').showModal();};
$('resetStandard').onclick=()=>{fillEditor(profiles.find(p=>p.id==='balanced-v1'));$('advancedSettings').open=false;};
$('priority').onchange=()=>{const weights=weightChoices[$('priority').value];if(weights)document.querySelectorAll('[data-weight]').forEach(x=>x.value=weights[x.dataset.weight]);updateWeightTotal();simpleSummary();};
$('strictness').onchange=()=>{const limits=scoreChoices[$('strictness').value];if(limits){$('acceptableCutoff').value=limits.acceptable;$('reviewCutoff').value=limits.review;}simpleSummary();};
function updateWeightTotal(){const total=[...document.querySelectorAll('[data-weight]')].reduce((s,x)=>s+Number(x.value),0);$('weightTotal').textContent='Total: '+total.toFixed(1)+'%';$('weightTotal').className=Math.abs(total-100)<0.000001?'valid-total':'invalid-total';}
$('weightFields').oninput=()=>{$('priority').value='custom';updateWeightTotal();simpleSummary();};
for(const id of ['acceptableCutoff','reviewCutoff'])$(id).oninput=()=>{$('strictness').value='custom';simpleSummary();};
$('closeProfile').onclick=()=>$('profileEditor').close();
$('profileForm').onsubmit=async e=>{
 e.preventDefault();const p=JSON.parse(JSON.stringify(editorBase));
 p.name=$('profileName').value.trim();p.cutoffs={acceptable:Number($('acceptableCutoff').value),review:Number($('reviewCutoff').value)};p.flatline_advisory=$('flatlineAdvisory').checked;
 document.querySelectorAll('[data-weight]').forEach(x=>p.weights[x.dataset.weight]=Number(x.value));document.querySelectorAll('[data-limit]').forEach(x=>p.limits[x.dataset.limit]=Number((Number(x.value)/limitSettings[x.dataset.limit][1]).toPrecision(12)));
 document.querySelectorAll('[data-fraction-max]').forEach(x=>p.fraction_bands[Number(x.dataset.fractionMax)].max=Number(x.value)/100);document.querySelectorAll('[data-fraction-score]').forEach(x=>p.fraction_bands[Number(x.dataset.fractionScore)].score=Number(x.value));
 document.querySelectorAll('[data-band-max]').forEach(x=>p.limit_bands[Number(x.dataset.bandMax)].max=Number(x.value));document.querySelectorAll('[data-band-score]').forEach(x=>p.limit_bands[Number(x.dataset.bandScore)].score=Number(x.value));
 $('saveProfile').disabled=true;
 try{const saved=await api('/api/profiles',{method:'POST',headers:{'Content-Type':'application/json','X-QC-Profile':'1'},body:JSON.stringify(p)});profiles.push(saved);activeProfile=saved.id;profileOptions();$('profileEditor').close();$('notice').textContent='Saved '+saved.name+'. The recorded issues remain unchanged.';await refresh();}catch(e){$('profileError').textContent=friendlyError(e.message);$('advancedSettings').open=true;}finally{$('saveProfile').disabled=false;}
};
$('uploadButton').onclick=()=>$('file').click();
$('file').onchange=()=>{
 const file=$('file').files[0];if(!file)return;
 if(!file.name.toLowerCase().endsWith('.mcap')){$('notice').textContent='Choose a recording file ending in .mcap.';return;}
 $('uploadButton').disabled=true;
 const xhr=new XMLHttpRequest();xhr.open('POST','/api/upload');xhr.setRequestHeader('X-QC-Upload','1');xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name));
 xhr.upload.onprogress=e=>{$('notice').textContent='Sending '+file.name+' to WSL: '+(e.lengthComputable?Math.round(e.loaded/e.total*100)+'%':'…');};
 xhr.onload=()=>{try{const d=JSON.parse(xhr.responseText);if(xhr.status!==202)throw Error(d.error);$('notice').textContent='Upload received. Saving the recording and starting its checks.';$('collection').value='all';refresh();pollJobs();}catch(e){$('notice').textContent=e.message;}finally{$('uploadButton').disabled=false;$('file').value='';}};
 xhr.onerror=()=>{$('notice').textContent='Upload connection failed. Retry the same file safely.';$('uploadButton').disabled=false;};xhr.send(file);
};
async function pollJobs(){try{const jobs=await api('/api/jobs');$('jobs').hidden=!jobs.length;$('jobRows').innerHTML=jobs.map(j=>'<p><strong>'+esc(j.name)+'</strong> · '+esc(({'Received':'Upload received','Storing raw data':'Saving your recording','Workflow submitted':'Checks started','Error':'Upload needs attention'}[j.state]||j.state))+(j.error?' · '+esc(j.error):'')+(j.digest?' · '+j.digest.slice(0,12):'')+'</p>').join('');}catch{}}
async function initialize(){try{const data=await api('/api/profiles');profiles=data.profiles;activeProfile=data.default;profileOptions();await refresh();}catch(e){$('notice').textContent=e.message;}}
initialize();pollJobs();setInterval(()=>{refresh();pollJobs();},15000);

function friendlyError(message){
 if(message.includes('Weights'))return 'Choose importance percentages from 0 to 100 that add up to 100%.';
 if(message.includes('cutoff'))return 'The score for meeting the standard must be higher than the score for checking before use.';
 if(message.includes('Band')||message.includes('bands'))return 'List problem amounts from smallest to largest. Marks should stay the same or get lower as problems increase.';
 if(message.includes('limits'))return 'Use positive amounts within the displayed range for every allowance.';
 if(message.includes('name'))return 'Give your standard a name between 1 and 60 characters.';
 return message;
}

$('profileForm').addEventListener('invalid',()=>{$('advancedSettings').open=true;},true);
