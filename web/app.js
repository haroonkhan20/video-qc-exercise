const $=id=>document.getElementById(id);
let records=[],filter='all',profiles=[],activeProfile='balanced-v1',selectedDigest=null,loadSequence=0,detailSequence=0;
const labels={pass:'Passed',fail:'Failed',needs_review:'Needs review',pending:'Pending'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const size=n=>n>=1e9?(n/1e9).toFixed(2)+' GB':(n/1e6).toFixed(1)+' MB';
const badge=v=>'<span class="badge '+(labels[v]?v:'pending')+'">'+(labels[v]||'Pending')+'</span>';
const gradeLabels={acceptable:'Acceptable under profile',review:'Review under profile',unacceptable:'Unacceptable under profile',not_assessed:'Not assessed'};
const marks=v=>v==null?'Not assessed':Number(v).toFixed(2)+'/10';
const gradeBadge=g=>g?'<strong class="grade-mark">'+marks(g.score)+'</strong><small class="grade-state '+g.recommendation+'">'+gradeLabels[g.recommendation]+'</small>':'<span class="grade-state">Pending</span>';
const names={integrity:'File integrity',inventory:'Required streams',decoding:'Video decoding',timing:'Timing continuity',alignment:'Coverage and synchronization',image:'Image quality',sensor:'Sensor validity'};
async function api(url,opts){const r=await fetch(url,opts),d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function render(){
 const base=records.filter(r=>$('collection').value==='all'||r.dataset==='mentor');
 $('total').textContent=base.length;
 for(const [id,v] of [['passes','pass'],['fails','fail'],['reviews','needs_review']])$(id).textContent=base.filter(r=>r.verdict===v).length;
 const search=$('search').value.toLowerCase(),rows=base.filter(r=>(filter==='all'||(r.verdict||'pending')===filter)&&($('gradeFilter').value==='all'||(r.grading?.recommendation||'not_assessed')===$('gradeFilter').value)&&(r.name+r.digest+(r.aliases||[]).join(' ')).toLowerCase().includes(search));
 $('count').textContent=rows.length;
 $('rows').innerHTML=rows.length?rows.map(r=>'<tr><td><strong>'+esc(r.name)+'</strong><small>SHA256 · '+r.digest.slice(0,16)+'…</small></td><td>'+badge(r.verdict)+'</td><td title="'+esc(r.grading?.why||'')+'">'+gradeBadge(r.grading)+'</td><td>'+esc((r.reason_codes||[]).join(', ')||(r.verdict?'No findings':r.workflow_state||'Awaiting result'))+'</td><td>'+size(r.bytes)+'</td><td>'+(r.verdict?'<button class="inspect" data-digest="'+r.digest+'">Inspect ↗</button>':esc(r.workflow_state||'Pending result'))+'</td></tr>').join(''):'<tr><td colspan="6">No recordings match this view.</td></tr>';
}
async function refresh(){
 const sequence=++loadSequence,profile=activeProfile;$('refresh').disabled=true;
 try{const d=await api('/api/recordings?profile='+encodeURIComponent(profile));if(sequence!==loadSequence)return;records=d.recordings;render();$('updated').textContent='Live worker data · '+new Date(d.updated_at*1000).toLocaleTimeString();}catch(e){if(sequence===loadSequence)$('notice').textContent=e.message+' Check make status if the cluster is stopped.';}finally{if(sequence===loadSequence)$('refresh').disabled=false;}
}
function gradingPanel(g){
 return '<section class="grade-panel"><div class="grade-heading"><div><div class="eyebrow">PROFILE ASSESSMENT · '+esc(g.profile.name)+'</div><strong class="overall-grade">'+marks(g.score)+'</strong><span>'+gradeLabels[g.recommendation]+'</span></div><div><p>Weighted average: '+(g.weighted_average==null?'not assessed':Number(g.weighted_average).toFixed(4)+'/10')+'</p>'+(g.critical_cap?'<p class="cap">Critical cap: 4/10 · '+esc(g.critical_cap.reasons.join(', '))+'</p>':'')+'</div></div><p>'+esc(g.why)+'</p>'+(g.score==null?'<p>Possible range from known evidence: '+g.possible_range[0]+'–'+g.possible_range[1]+'. No complete grade is issued.</p>':'')+'<p class="grade-scope">10 means no measured penalty under this standard. Acceptance here does not override the original verdict. Image/gap grading uses already detected runs, not new detection thresholds.</p>'+g.categories.map(c=>'<details class="category"><summary><span>'+esc(c.name)+'</span><strong>'+marks(c.score)+'</strong><small>'+c.weight+'% weight · '+(c.contribution==null?'contribution unknown':Number(c.contribution).toFixed(3)+' points')+'</small></summary><p>'+esc(c.why)+(c.worst_stream?'. Worst measured stream: '+esc(c.worst_stream):'')+'</p>'+c.streams.map(s=>'<details class="stream-grade"><summary>'+esc(s.topic)+' · '+marks(s.score)+'</summary><p>'+esc(s.why)+'</p><div class="table-wrap"><table><thead><tr><th>PARAMETER</th><th>MARK</th><th>WHY AND MEASUREMENTS</th></tr></thead><tbody>'+s.parameters.map(p=>'<tr><td>'+esc(p.parameter)+'</td><td>'+(!p.applicable?'Not applicable':marks(p.score))+'</td><td>'+esc(p.why)+(p.measured!=null?'<div class="mono">Measured: '+esc(JSON.stringify(p.measured))+'</div>':'')+(p.limit!=null?'<div class="mono">Allowed: '+esc(JSON.stringify(p.limit))+'</div>':'')+'</td></tr>').join('')+'</tbody></table></div></details>').join('')+'</details>').join('')+'<a class="download" id="gradeDownload">Download grade and profile JSON ↓</a><p class="mono">Profile version: '+esc(g.profile_version)+'<br>Grading engine: '+esc(g.engine_version)+'<br>Evidence fingerprint: '+esc(g.source_report_hash)+'</p></section>';
}
const descriptions={BLACK_RUN:'Images stayed very dark. Inspect the scene to understand why.',BRIGHT_RUN:'Images stayed very bright. Check whether the scene explains this.',SENSOR_FLATLINE:'The sensor value stayed unchanged. A stationary gripper can be legitimate.',FROZEN_RUN:'Images changed very little. Check whether the scene was stationary.',BLUR_RUN:'Low image sharpness was detected. Inspect the scene and focus.',GAP_RUN:'A long interval between recorded messages was detected.',COVERAGE_MISMATCH:'A stream started late or ended early beyond the allowed boundary.',CHECK_UNAVAILABLE:'A required check could not finish. This is not evidence of healthy data.'};
async function detail(digest){
 selectedDigest=digest;const sequence=++detailSequence;
 const selected=records.find(r=>r.digest===digest);$('detailTitle').textContent=selected?.name||digest.slice(0,12);$('detailBody').textContent='Loading report and grade…';if(!$('detail').open)$('detail').showModal();
 try{
 const [r,g]=await Promise.all([api('/api/reports/'+digest),api('/api/grades/'+digest+'?profile='+encodeURIComponent(activeProfile))]);if(sequence!==detailSequence)return;
 $('detailBody').innerHTML='<p>Original QC verdict: '+badge(r.verdict)+'</p>'+gradingPanel(g)+'<div class="detail-summary"><strong>Follow the original evidence</strong><p>Decision → reason → stream → time interval → configured threshold.</p><p>Original coverage allows '+esc(r.config.timing.coverage_start_tolerance_seconds)+' seconds at startup and '+esc(r.config.timing.coverage_end_tolerance_seconds)+' seconds at the end. Camera synchronization limit: '+esc(r.config.timing.camera_sync_skew_ms)+' ms.</p></div><h2>Findings ('+r.findings.length+')</h2>'+
 (r.findings.length?r.findings.map(f=>'<article class="finding"><strong>'+esc(f.code)+'</strong><p>'+esc(descriptions[f.code]||'A configured rule was triggered. Consult the JSON report for measurements and policy.')+'</p><code>'+esc(f.stream||'Recording container')+'</code><p>'+(f.start_s!=null?Number(f.start_s).toFixed(2)+'–'+Number(f.end_s).toFixed(2)+' seconds into the recording':'Recording-level finding')+'</p><code>'+esc(JSON.stringify(f.metrics||{}))+'</code></article>').join(''):'<p>No configured checks flagged a problem. This does not rule out every possible defect.</p>')+
  '<section class="samples"><h2>Camera evidence</h2><p>Sampled images, about one per second. Captions show the actual sample time.</p><div class="sample-controls"><label>Seconds into recording <input id="sampleTime" type="number" min="0" max="86400" step="0.1" value="0"></label><button id="loadSamples">Show images</button></div><div id="sampleGrid"></div></section><h2 style="margin-top:22px">Stream measurements</h2><div class="table-wrap"><table><thead><tr><th>STREAM</th><th>MESSAGES</th><th>RATE / SECOND</th><th>DECODE ERRORS</th><th>EST. DROPS</th></tr></thead><tbody>'+r.streams.map(s=>'<tr><td>'+esc(s.topic)+'</td><td>'+esc(s.timing?.log?.messages??'—')+'</td><td>'+(s.timing?.log?.effective_hz==null?'—':Number(s.timing.log.effective_hz).toFixed(2))+'</td><td>'+esc(s.stats?.video_decode_errors??'—')+'</td><td>'+esc(s.timing?.log?.estimated_dropped_frames??'—')+'</td></tr>').join('')+'</tbody></table></div><a class="download" id="download">Download full JSON report ↓</a><p class="mono">Recording: '+esc(r.digest)+'<br>Rules: '+esc(r.config_version)+'<br>Software: '+esc(r.code_version)+'</p>';
 const initial=r.findings.find(f=>f.start_s!=null);
 $('sampleTime').value=initial?((initial.start_s+initial.end_s)/2).toFixed(2):0;
 $('loadSamples').onclick=async()=>{
  const t=Number($('sampleTime').value);if(!Number.isFinite(t)||t<0||t>86400)return;
  $('loadSamples').disabled=true;$('sampleGrid').textContent='Loading camera samples…';
  try{const frames=await api('/api/samples/'+digest+'/'+t.toFixed(3));$('sampleGrid').innerHTML=frames.length?frames.map(f=>'<figure><img alt="'+esc(f.topic)+' at '+Number(f.seconds).toFixed(2)+' seconds" src="data:image/jpeg;base64,'+f.image+'"><figcaption>'+esc(f.topic)+'<br>'+Number(f.seconds).toFixed(2)+' seconds</figcaption></figure>').join(''):'No camera samples available for this recording.';}catch(e){$('sampleGrid').textContent=e.message;}finally{$('loadSamples').disabled=false;}
 };
 for(const [id,data,suffix] of [['download',r,'.json'],['gradeDownload',g,'.grade.json']]){const link=$(id);link.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));link.download=(selected?.name||digest+'.mcap').replace(/\.mcap$/,suffix);}
 }catch(e){$('detailBody').textContent=e.message;}
}
$('close').onclick=()=>$('detail').close();
$('rows').onclick=e=>{const b=e.target.closest('[data-digest]');if(b)detail(b.dataset.digest);};
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('selected',x===b));render();});
$('search').oninput=render;$('collection').onchange=render;$('refresh').onclick=refresh;
$('gradeFilter').onchange=render;
$('profile').onchange=()=>{activeProfile=$('profile').value;refresh();if($('detail').open&&selectedDigest)detail(selectedDigest);};
function profileOptions(){ $('profile').innerHTML=profiles.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+' · '+p.version.slice(0,8)+'</option>').join('');$('profile').value=activeProfile; }
const limitNames={rate_relative_tolerance:'Rate deviation fraction (0.3 = 30%)',payload_stamp_tolerance_ms:'Payload timestamp offset (ms)',coverage_start_tolerance_seconds:'Startup lag (seconds)',coverage_end_tolerance_seconds:'End lag (seconds)',camera_sync_skew_ms:'Camera skew (ms)',camera_sync_drift_ms:'Camera drift (ms)'};
$('customize').onclick=()=>{
 const p=profiles.find(x=>x.id===activeProfile);if(!p)return;
 $('profileName').value=p.name+' copy';$('acceptableCutoff').value=p.cutoffs.acceptable;$('reviewCutoff').value=p.cutoffs.review;$('flatlineAdvisory').checked=p.flatline_advisory;$('profileError').textContent='';
 $('weightFields').innerHTML=Object.entries(p.weights).map(([k,v])=>'<label>'+names[k]+' (%) <input data-weight="'+k+'" type="number" min="0" max="100" step="0.1" value="'+v+'" required></label>').join('');
 $('limitFields').innerHTML=Object.entries(p.limits).map(([k,v])=>'<label>'+limitNames[k]+' <input data-limit="'+k+'" type="number" min="0.000001" max="86400" step="any" value="'+v+'" required></label>').join('');
 $('fractionFields').innerHTML=p.fraction_bands.map((b,i)=>'<div><label>Upper affected fraction (%) <input data-fraction-max="'+i+'" type="number" min="0" max="100" step="any" value="'+b.max*100+'" '+(i===0||i===p.fraction_bands.length-1?'readonly':'')+' required></label><label>Mark / 10 <input data-fraction-score="'+i+'" type="number" min="0" max="10" step="0.1" value="'+b.score+'" '+(i===0||i===p.fraction_bands.length-1?'readonly':'')+' required></label></div>').join('');
 $('limitBandFields').innerHTML=p.limit_bands.map((b,i)=>'<div><label>Upper limit multiple <input data-band-max="'+i+'" type="number" min="1" step="any" value="'+b.max+'" '+(i===0?'readonly':'')+' required></label><label>Mark / 10 <input data-band-score="'+i+'" type="number" min="0" max="10" step="0.1" value="'+b.score+'" '+(i===0?'readonly':'')+' required></label></div>').join('');
 updateWeightTotal();$('profileEditor').showModal();
};
function updateWeightTotal(){const total=[...document.querySelectorAll('[data-weight]')].reduce((s,x)=>s+Number(x.value),0);$('weightTotal').textContent='Total: '+total.toFixed(1)+'%';$('weightTotal').className=Math.abs(total-100)<0.000001?'valid-total':'invalid-total';}
$('weightFields').oninput=updateWeightTotal;
$('closeProfile').onclick=()=>$('profileEditor').close();
$('profileForm').onsubmit=async e=>{
 e.preventDefault();const source=profiles.find(x=>x.id===activeProfile),p=JSON.parse(JSON.stringify(source));delete p.version;
 p.name=$('profileName').value.trim();p.cutoffs={acceptable:Number($('acceptableCutoff').value),review:Number($('reviewCutoff').value)};p.flatline_advisory=$('flatlineAdvisory').checked;
 document.querySelectorAll('[data-weight]').forEach(x=>p.weights[x.dataset.weight]=Number(x.value));document.querySelectorAll('[data-limit]').forEach(x=>p.limits[x.dataset.limit]=Number(x.value));
 document.querySelectorAll('[data-fraction-max]').forEach(x=>p.fraction_bands[Number(x.dataset.fractionMax)].max=Number(x.value)/100);document.querySelectorAll('[data-fraction-score]').forEach(x=>p.fraction_bands[Number(x.dataset.fractionScore)].score=Number(x.value));
 document.querySelectorAll('[data-band-max]').forEach(x=>p.limit_bands[Number(x.dataset.bandMax)].max=Number(x.value));document.querySelectorAll('[data-band-score]').forEach(x=>p.limit_bands[Number(x.dataset.bandScore)].score=Number(x.value));
 $('saveProfile').disabled=true;
 try{const saved=await api('/api/profiles',{method:'POST',headers:{'Content-Type':'application/json','X-QC-Profile':'1'},body:JSON.stringify(p)});profiles.push(saved);activeProfile=saved.id;profileOptions();$('profileEditor').close();$('notice').textContent='Saved '+saved.name+'. Original QC verdicts remain unchanged.';await refresh();}catch(e){$('profileError').textContent=e.message;}finally{$('saveProfile').disabled=false;}
};
$('uploadButton').onclick=()=>$('file').click();
$('file').onchange=()=>{
 const file=$('file').files[0];if(!file)return;
 if(!file.name.toLowerCase().endsWith('.mcap')){$('notice').textContent='Choose an MCAP recording.';return;}
 $('uploadButton').disabled=true;
 const xhr=new XMLHttpRequest();xhr.open('POST','/api/upload');xhr.setRequestHeader('X-QC-Upload','1');xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name));
 xhr.upload.onprogress=e=>{$('notice').textContent='Sending '+file.name+' to WSL: '+(e.lengthComputable?Math.round(e.loaded/e.total*100)+'%':'…');};
 xhr.onload=()=>{try{const d=JSON.parse(xhr.responseText);if(xhr.status!==202)throw Error(d.error);$('notice').textContent='File received. Storing protected raw data, then starting its QC workflow.';$('collection').value='all';refresh();pollJobs();}catch(e){$('notice').textContent=e.message;}finally{$('uploadButton').disabled=false;$('file').value='';}};
 xhr.onerror=()=>{$('notice').textContent='Upload connection failed. Retry the same file safely.';$('uploadButton').disabled=false;};xhr.send(file);
};
async function pollJobs(){try{const jobs=await api('/api/jobs');$('jobs').hidden=!jobs.length;$('jobRows').innerHTML=jobs.map(j=>'<p><strong>'+esc(j.name)+'</strong> · '+esc(j.state)+(j.error?' · '+esc(j.error):'')+(j.digest?' · '+j.digest.slice(0,12):'')+'</p>').join('');}catch{}}
async function initialize(){try{const data=await api('/api/profiles');profiles=data.profiles;activeProfile=data.default;profileOptions();await refresh();}catch(e){$('notice').textContent=e.message;}}
initialize();pollJobs();setInterval(()=>{refresh();pollJobs();},15000);
