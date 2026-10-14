const $=id=>document.getElementById(id);
let records=[],filter='all',busy=false;
const labels={pass:'Passed',fail:'Failed',needs_review:'Needs review',pending:'Pending'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const size=n=>n>=1e9?(n/1e9).toFixed(2)+' GB':(n/1e6).toFixed(1)+' MB';
const badge=v=>'<span class="badge '+(labels[v]?v:'pending')+'">'+(labels[v]||'Pending')+'</span>';
async function api(url,opts){const r=await fetch(url,opts),d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function render(){
 const base=records.filter(r=>$('collection').value==='all'||r.dataset==='mentor');
 $('total').textContent=base.length;
 for(const [id,v] of [['passes','pass'],['fails','fail'],['reviews','needs_review']])$(id).textContent=base.filter(r=>r.verdict===v).length;
 const search=$('search').value.toLowerCase(),rows=base.filter(r=>(filter==='all'||(r.verdict||'pending')===filter)&&(r.name+r.digest+(r.aliases||[]).join(' ')).toLowerCase().includes(search));
 $('count').textContent=rows.length;
 $('rows').innerHTML=rows.length?rows.map(r=>'<tr><td><strong>'+esc(r.name)+'</strong><small>SHA256 · '+r.digest.slice(0,16)+'…</small></td><td>'+badge(r.verdict)+'</td><td>'+esc((r.reason_codes||[]).join(', ')||(r.verdict?'No findings':r.workflow_state||'Awaiting result'))+'</td><td>'+size(r.bytes)+'</td><td>'+(r.verdict?'<button class="inspect" data-digest="'+r.digest+'">Inspect ↗</button>':esc(r.workflow_state||'Pending result'))+'</td></tr>').join(''):'<tr><td colspan="5">No recordings match this view.</td></tr>';
}
async function refresh(){
 if(busy)return;busy=true;$('refresh').disabled=true;
 try{const d=await api('/api/recordings');records=d.recordings;render();$('updated').textContent='Live worker data · '+new Date(d.updated_at*1000).toLocaleTimeString();}catch(e){$('notice').textContent=e.message+' Run make up if the cluster is stopped.';}finally{busy=false;$('refresh').disabled=false;}
}
const descriptions={BLACK_RUN:'Images stayed very dark. Inspect the scene to understand why.',BRIGHT_RUN:'Images stayed very bright. Check whether the scene explains this.',SENSOR_FLATLINE:'The sensor value stayed unchanged. A stationary gripper can be legitimate.',FROZEN_RUN:'Images changed very little. Check whether the scene was stationary.',BLUR_RUN:'Low image sharpness was detected. Inspect the scene and focus.',GAP_RUN:'A long interval between recorded messages was detected.',COVERAGE_MISMATCH:'A stream started late or ended early beyond the allowed boundary.',CHECK_UNAVAILABLE:'A required check could not finish. This is not evidence of healthy data.'};
async function detail(digest){
 const selected=records.find(r=>r.digest===digest);$('detailTitle').textContent=selected?.name||digest.slice(0,12);$('detailBody').textContent='Loading report…';$('detail').showModal();
 try{
 const r=await api('/api/reports/'+digest);
 $('detailBody').innerHTML=badge(r.verdict)+'<div class="detail-summary"><strong>Follow the evidence</strong><p>Decision → reason → stream → time interval → configured threshold.</p><p>Coverage allows '+esc(r.config.timing.coverage_start_tolerance_seconds)+' seconds at startup and '+esc(r.config.timing.coverage_end_tolerance_seconds)+' seconds at the end. Camera synchronization limit: '+esc(r.config.timing.camera_sync_skew_ms)+' ms.</p></div><h2>Findings ('+r.findings.length+')</h2>'+
 (r.findings.length?r.findings.map(f=>'<article class="finding"><strong>'+esc(f.code)+'</strong><p>'+esc(descriptions[f.code]||'A configured rule was triggered. Consult the JSON report for measurements and policy.')+'</p><code>'+esc(f.stream||'Recording container')+'</code><p>'+(f.start_s!=null?Number(f.start_s).toFixed(2)+'–'+Number(f.end_s).toFixed(2)+' seconds into the recording':'Recording-level finding')+'</p><code>'+esc(JSON.stringify(f.metrics||{}))+'</code></article>').join(''):'<p>No configured checks flagged a problem. This does not rule out every possible defect.</p>')+
  '<section class="samples"><h2>Camera evidence</h2><p>Sampled images, about one per second. Captions show the actual sample time.</p><div class="sample-controls"><label>Seconds into recording <input id="sampleTime" type="number" min="0" max="86400" step="0.1" value="0"></label><button id="loadSamples">Show images</button></div><div id="sampleGrid"></div></section><h2 style="margin-top:22px">Stream measurements</h2><div class="table-wrap"><table><thead><tr><th>STREAM</th><th>MESSAGES</th><th>RATE / SECOND</th><th>DECODE ERRORS</th><th>EST. DROPS</th></tr></thead><tbody>'+r.streams.map(s=>'<tr><td>'+esc(s.topic)+'</td><td>'+esc(s.timing?.log?.messages??'—')+'</td><td>'+(s.timing?.log?.effective_hz==null?'—':Number(s.timing.log.effective_hz).toFixed(2))+'</td><td>'+esc(s.stats?.video_decode_errors??'—')+'</td><td>'+esc(s.timing?.log?.estimated_dropped_frames??'—')+'</td></tr>').join('')+'</tbody></table></div><a class="download" id="download">Download full JSON report ↓</a><p class="mono">Recording: '+esc(r.digest)+'<br>Rules: '+esc(r.config_version)+'<br>Software: '+esc(r.code_version)+'</p>';
 const initial=r.findings.find(f=>f.start_s!=null);
 $('sampleTime').value=initial?((initial.start_s+initial.end_s)/2).toFixed(2):0;
 $('loadSamples').onclick=async()=>{
  const t=Number($('sampleTime').value);if(!Number.isFinite(t)||t<0||t>86400)return;
  $('loadSamples').disabled=true;$('sampleGrid').textContent='Loading camera samples…';
  try{const frames=await api('/api/samples/'+digest+'/'+t.toFixed(3));$('sampleGrid').innerHTML=frames.length?frames.map(f=>'<figure><img alt="'+esc(f.topic)+' at '+Number(f.seconds).toFixed(2)+' seconds" src="data:image/jpeg;base64,'+f.image+'"><figcaption>'+esc(f.topic)+'<br>'+Number(f.seconds).toFixed(2)+' seconds</figcaption></figure>').join(''):'No camera samples available for this recording.';}catch(e){$('sampleGrid').textContent=e.message;}finally{$('loadSamples').disabled=false;}
 };
 const link=$('download');link.href=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));link.download=(selected?.name||digest+'.mcap').replace(/\.mcap$/,'.json');
 link.onclick=()=>setTimeout(()=>URL.revokeObjectURL(link.href),1000);
 }catch(e){$('detailBody').textContent=e.message;}
}
$('close').onclick=()=>$('detail').close();
$('rows').onclick=e=>{const b=e.target.closest('[data-digest]');if(b)detail(b.dataset.digest);};
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('selected',x===b));render();});
$('search').oninput=render;$('collection').onchange=render;$('refresh').onclick=refresh;
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
refresh();pollJobs();setInterval(()=>{refresh();pollJobs();},15000);
