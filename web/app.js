const $=id=>document.getElementById(id);
let records=[],filter='all',profiles=[],activeProfile='balanced-v1',selectedDigest=null,loadSequence=0,detailSequence=0;
const labels={pass:'Passed checks',fail:'Issues found',needs_review:'Needs a look',pending:'Waiting for results'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const size=n=>n>=1e9?(n/1e9).toFixed(2)+' GB':(n/1e6).toFixed(1)+' MB';
const badge=v=>'<span class="badge '+(labels[v]?v:'pending')+'">'+(labels[v]||'Pending')+'</span>';
const gradeLabels={acceptable:'Meets this standard',review:'Check before use',unacceptable:'Issues found',not_assessed:'Check not finished'};
const marks=v=>v==null?'No rating':Number(v).toFixed(2)+'/10';
const gradeBadge=g=>g&&g.score==null&&['blocked_by_fault','limited_evidence'].includes(g.assessment_state)?'<strong class="grade-mark">Cannot rate</strong><small class="grade-state">'+(g.assessment_state==='blocked_by_fault'?'File or data fault prevents a full rating':'Checked; evidence is incomplete')+'</small>':g?'<strong class="grade-mark">'+marks(g.score)+'</strong><small class="grade-state '+g.recommendation+'">'+gradeLabels[g.recommendation]+'</small>':'<span class="grade-state">Pending</span>';
const names=Friendly.areas;
let editorBase=null;
let headMotionEnabled=false,headScanningEnabled=false;
async function api(url,opts){const r=await fetch(url,opts),d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function render(){
 const base=records.filter(r=>$('collection').value==='all'||r.dataset==='reference');
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
function problemButton(topic,start,end){
 if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>86400)return '';
 return '<button class="show-problem" data-problem-topic="'+esc(topic||'')+'" data-problem-start="'+start+'" data-problem-end="'+end+'">Show me the problem ↗</button>';
}
function timelinePanel(report,obstruction,head=null){
 const source=head?{...report,findings:[...report.findings,...head.findings.filter(f=>f.severity!=='source_policy')]}:report;
 const timeline=IssueTimeline.model(source,obstruction);
 const label=code=>code==='POSSIBLE_OBSTRUCTION'?'Possible blocked view':Friendly.issues[code]||code.replaceAll('_',' ').toLowerCase();
 const time=value=>Number(value).toFixed(2)+'s';
 let html='<section class="issue-timeline" aria-labelledby="timelineTitle"><h2 id="timelineTitle">Where are the problems?</h2><p>Read from the start to the end of the recording. Each coloured mark is a flagged moment. Select a mark or its time to see saved camera images.</p>';
 if(timeline.duration!=null){
  html+='<div class="timeline-axis"><span>Start · 0s</span><span>'+time(timeline.duration/2)+'</span><span>End · '+time(timeline.duration)+'</span></div>';
  html+=timeline.groups.map(group=>'<div class="timeline-row"><div class="timeline-label"><strong>'+esc(label(group.code))+'</strong><small>'+esc(Friendly.stream(group.stream))+'</small></div><div class="timeline-tracks">'+group.lanes.map(lane=>'<div class="timeline-track">'+lane.map(item=>{
   const title=label(item.code)+' · '+Friendly.stream(item.stream)+' · '+time(item.start)+(item.end===item.start?'':'–'+time(item.end));
   return '<button class="timeline-mark '+(item.code==='POSSIBLE_OBSTRUCTION'?'timeline-review':'')+'" style="left:'+item.left+'%;width:'+item.width+'%" title="'+esc(title)+'" aria-label="Show problem: '+esc(title)+'" data-problem-topic="'+esc(item.stream)+'" data-problem-start="'+item.start+'" data-problem-end="'+item.end+'"><span class="sr-only">'+esc(title)+'</span></button>';
  }).join('')+'</div>').join('')+'</div><small class="timeline-times">'+group.items.map(item=>'<button class="timeline-time" data-problem-topic="'+esc(item.stream)+'" data-problem-start="'+item.start+'" data-problem-end="'+item.end+'">'+time(item.start)+(item.end===item.start?'':'–'+time(item.end))+'</button>').join(' ')+'</small></div>').join('');
  if(!timeline.groups.length)html+='<p class="timeline-empty">No timed issues were reported. This does not mean every check completed; see the check result and ratings below.</p>';
  if(timeline.groups.length)html+='<p class="timeline-note">Short marks are widened so they are easy to select. The written times give the actual interval. Unmarked areas have no reported timed issue; they are not a guarantee of perfect data.</p>';
 }else html+='<p>The recording length is unavailable, so we cannot position issues on a timeline.</p>';
 if(timeline.untimed.length)html+='<div class="timeline-untimed"><strong>Other issues — no exact time available</strong><ul>'+timeline.untimed.map(f=>'<li>'+esc(label(f.code))+' · '+esc(Friendly.stream(f.stream))+'</li>').join('')+'</ul></div>';
 if(!timeline.obstructionChecked)html+='<p class="timeline-note">The possible blocked-view check has not completed. Its results will appear here after you run it.</p>';
 return html+'</section>';
}
const reviewLabels={confirmed_problem:'Confirmed problem',normal_scene:'Normal scene',unsure:'Unsure'};
function reviewPanel(item){
 if(!item)return '<p class="review-status">Review is unavailable for this finding. Refresh the report to try again.</p>';
 const saved=item.review;
 return '<form class="issue-review" data-review-id="'+item.id+'"><h4>Your review</h4><p>Keep your assessment here. The original automatic finding and score stay unchanged.</p><label>Decision<select name="decision" required><option value="">Choose a review…</option>'+Object.entries(reviewLabels).map(([value,label])=>'<option value="'+value+'"'+(saved?.decision===value?' selected':'')+'>'+label+'</option>').join('')+'</select></label><label>Note (optional)<textarea name="note" maxlength="2000" rows="3" placeholder="What did you observe?">'+esc(saved?.note||'')+'</textarea></label><button type="submit">Save review</button><p class="review-status" role="status">'+(saved?'Saved: '+esc(reviewLabels[saved.decision])+' · '+esc(new Date(saved.created_at).toLocaleString()):'Not reviewed yet.')+'</p>'+
 (item.history.length?'<details><summary>Review history ('+item.history.length+')</summary>'+item.history.map(h=>'<p><strong>'+esc(reviewLabels[h.decision])+'</strong> · '+esc(new Date(h.created_at).toLocaleString())+'<br>'+esc(h.note||'No note')+'</p>').join('')+'</details>':'')+'</form>';
}
function gradingPanel(g){
 const card=g.scorecard;
 if(!card)return '<p>This report needs the current dashboard version.</p>';
 const why=a=>{
  if(a.score==null)return card.assessment_state==='blocked_by_fault'?'File or data faults prevent a reliable rating for this aspect.':'There is not enough evidence for a reliable rating. Missing information is never given 10.';
  const worst=[...a.streams].sort((x,y)=>x.score-y.score)[0];
  const parameter=worst?.parameters?.filter(p=>p.applicable!==false).sort((x,y)=>x.score-y.score)[0];
  if(parameter)return Friendly.why(parameter);
  if(a.id==='integrity')return a.score===10?'The file inspection found no structural problem.':'The file is damaged or incomplete. Check the original findings below.';
  if(a.id==='inventory')return a.score===10?'All required cameras and sensors were present in the expected format.':'A required camera or sensor is missing or uses an unexpected format.';
  if(a.id==='decoding')return a.score===10?'All required videos could be read without a playback fault.':'Some video could not be read correctly. Check the affected camera below.';
  return worst?.why||a.why;
 };
 return '<section class="grade-panel"><div class="eyebrow">CHOSEN STANDARD · '+esc(g.profile.id==='balanced-v1'?'Default':g.profile.name)+'</div><h2>Overall Score</h2><strong class="overall-grade">'+marks(card.score)+'</strong><p>'+(card.assessment_state==='blocked_by_fault'?'Issues found — a full rating is unavailable':gradeLabels[card.recommendation])+'</p>'+
 '<h3>What makes up this score?</h3><p>Each aspect below has a mark out of 10. The Overall Score starts from these ratings, then applies a limit if a serious issue was found. Aspects with a higher importance count more. Each aspect averages the required cameras or sensors; its explanation highlights the lowest mark.</p>'+
 (g.original_verdict!=='pass'?'<p class="attention-note">The original checks found issues. A high score does not clear them: review the flagged moments below before using this recording.</p>':'')+
 (card.serious_issue_limit?'<div class="cap"><h3>Why is the Overall Score limited?</h3><p>'+esc(card.serious_issue_limit.explanations.join(' '))+'</p><p>'+ (card.weighted_average==null?'Required checks are incomplete. No final score is issued.':'Calculated score: <strong>'+Number(card.weighted_average).toFixed(2)+'/10</strong>. Overall Score: <strong>'+marks(card.score)+'</strong>.')+'</p><p>This issue sets a maximum of '+card.serious_issue_limit.limit+'/10. '+(card.serious_issue_limit.applied?'Good ratings elsewhere cannot clear it.':'A lower calculated score stays lower; the limit never increases a score.')+'</p></div>':'')+
 (card.review_limit?'<p class="attention-note">'+esc(card.review_limit.why)+(card.weighted_average==null?'':' Calculated rating before this limit: '+Number(card.weighted_average).toFixed(2)+'/10.')+'</p>':'')+
 (card.assessment_state==='blocked_by_fault'?'<p class="attention-note">This recording was checked. Its file or data faults prevent some required checks from completing, so those aspects have no rating. The automatic failure still applies.</p>':'')+
 (card.possible_obstruction?'<p class="attention-note">A possible blocked view needs a look before use. A dark object in the scene can also cause this warning.</p>':'')+
 (!card.assessment_complete&&card.assessment_state!=='blocked_by_fault'?'<p class="attention-note">'+(card.head_motion&&(card.head_motion.status!=='checked'||card.head_motion.severity==='not_assessed')?'Head movement has insufficient evidence for a complete rating. See the Head movement section.':card.assessment_state==='limited_evidence'?'The check ran, but the retained evidence cannot support a complete rating. You can retry the snapshot check; missing evidence is never given a perfect score.':'The Overall Score is waiting for complete information. Use Check for a blocked view below to check the saved camera snapshots.')+'</p>':'')+
 '<div class="aspect-grid">'+card.aspects.map(a=>'<article class="aspect-card"><div class="aspect-heading"><h3>'+esc(a.name)+'</h3><strong>'+marks(a.score)+'</strong></div><p>'+esc(why(a))+'</p><small>Importance: '+Number(a.weight.toFixed(2))+'%'+(a.contribution==null?'':' · Adds '+a.contribution.toFixed(2)+' points before serious-issue limits')+'</small><details><summary>Camera and sensor breakdown</summary>'+a.streams.map(t=>'<p><strong>'+esc(Friendly.stream(t.topic))+'</strong> · '+marks(t.score)+'<br>'+esc(t.parameters?.length?Friendly.why([...t.parameters].filter(p=>p.applicable!==false).sort((x,y)=>x.score-y.score)[0]):t.why)+'</p>'+((t.evidence?.runs||[]).map(r=>'<p>Possible blockage: '+r.start_s.toFixed(1)+'–'+r.end_s.toFixed(1)+' seconds; up to '+Math.round(r.maximum_area_fraction*100)+'% of the picture.</p>'+problemButton(t.topic,r.start_s,r.end_s)).join(''))).join('')+'</details></article>').join('')+'</div>'+
 '<h3>Check for a blocked view</h3><p>Checks saved snapshots, about one per second, for a persistent dark area covering part of the picture. This can miss brief or non-dark blockages. It is a review aid, not proof of an obstruction.</p><button id="checkObstruction">Check saved snapshots</button><p id="obstructionStatus" role="status">'+(card.obstruction.status==='checked'?'Saved snapshots checked. Results are included above.':'This additional check has not completed for this recording.')+'</p>'+
 '<p class="grade-scope">10 means no measured reason to lower this mark under your chosen standard. It does not guarantee a perfect recording. The original automatic findings remain below.</p><a class="download" id="gradeDownload">Download score report</a><details class="technical"><summary>Calculation and version details</summary><pre>'+esc(JSON.stringify({model:card.model,weights:card.aspects.map(a=>({aspect:a.name,weight:a.weight,score:a.score,contribution:a.contribution})),beforeCap:card.weighted_average,review_limit:card.review_limit,serious_issue_limit:card.serious_issue_limit,profile_version:g.profile_version,source_report_hash:g.source_report_hash,detector:card.obstruction.detector,legacy_category_grade:g.legacy_category_grade},null,2))+'</pre></details></section>';
}
const descriptions={BLACK_RUN:'Images stayed very dark. Inspect the scene to understand why.',BRIGHT_RUN:'Images stayed very bright. Check whether the scene explains this.',SENSOR_FLATLINE:'The sensor value stayed unchanged. A stationary gripper can be legitimate.',FROZEN_RUN:'Images changed very little. Check whether the scene was stationary.',BLUR_RUN:'Low image sharpness was detected. Inspect the scene and focus.',GAP_RUN:'A long interval between recorded messages was detected.',COVERAGE_MISMATCH:'A stream started late or ended early beyond the allowed boundary.',CHECK_UNAVAILABLE:'A required check could not finish. This is not evidence of healthy data.'};
async function detail(digest){
 selectedDigest=digest;const sequence=++detailSequence;
 const selected=records.find(r=>r.digest===digest);$('detailTitle').textContent=selected?.name||digest.slice(0,12);$('detailBody').textContent='Loading report and grade…';if(!$('detail').open)$('detail').showModal();
 try{
 const [r,g,reviewData]=await Promise.all([api('/api/reports/'+digest),api('/api/grades/'+digest+'?profile='+encodeURIComponent(activeProfile)),api('/api/reviews/'+digest).catch(e=>({error:e.message,issues:[]}))]);if(sequence!==detailSequence)return;
 $('detailBody').innerHTML='<p>Automatic check result: '+badge(r.verdict)+'</p><div id="timelinePanel">'+timelinePanel(r,g.scorecard?.obstruction,g.scorecard?.head_motion)+'</div><div id="headPanel">'+(headMotionEnabled?HeadMotionUI.render(g.scorecard?.head_motion,headScanningEnabled):'')+'</div><div id="scorecard">'+gradingPanel(g)+'</div><h2>What needs attention ('+r.findings.length+')</h2>'+
 (r.findings.length?r.findings.map((f,index)=>'<article class="finding"><strong>'+esc(Friendly.issues[f.code]||'An issue needs attention')+'</strong><p>'+esc(descriptions[f.code]||'This check found a problem. See the affected moments and optional technical details.')+'</p><p>'+esc(Friendly.stream(f.stream))+'</p><p>'+(f.start_s!=null?Number(f.start_s).toFixed(2)+'–'+Number(f.end_s).toFixed(2)+' seconds into the recording':'Applies to the whole recording')+'</p>'+problemButton(f.stream,f.start_s,f.end_s)+'<details class="technical"><summary>Technical details</summary><pre>'+esc(JSON.stringify(f,null,2))+'</pre></details><div data-review-mount="'+index+'">'+reviewPanel(reviewData.issues.find(item=>item.origin==='automatic'&&item.finding_index===index))+'</div></article>').join(''):'<p>The automatic checks did not find an issue under their current rules.</p>')+
  '<div id="obstructionReviews"></div><div id="headReviews"></div><p id="reviewNotice" role="status"></p><div id="previousReviewHistory"></div><a class="download" id="reviewDownload">Download human reviews</a><section class="samples" id="problemImages"><h2 id="sampleHeading" tabindex="-1">Look at the recording</h2><p>These are saved snapshots, about one per second. The time below each picture is when it was taken.</p><div class="sample-controls"><label>Seconds into recording <input id="sampleTime" type="number" min="0" max="86400" step="0.1" value="0"></label><button id="loadSamples">Show images</button></div><p id="sampleContext" role="status" aria-live="polite"></p><div id="sampleGrid" aria-busy="false"></div></section><details class="technical"><summary>Detailed camera and sensor measurements</summary><div class="table-wrap"><table><thead><tr><th>CAMERA OR SENSOR</th><th>READINGS</th><th>READINGS / SECOND</th><th>PLAYBACK ERRORS</th><th>EST. MISSING READINGS</th></tr></thead><tbody>'+r.streams.map(s=>'<tr><td>'+esc(Friendly.stream(s.topic))+'</td><td>'+esc(s.timing?.log?.messages??'—')+'</td><td>'+(s.timing?.log?.effective_hz==null?'—':Number(s.timing.log.effective_hz).toFixed(2))+'</td><td>'+esc(s.stats?.video_decode_errors??'—')+'</td><td>'+esc(s.timing?.log?.estimated_dropped_frames??'—')+'</td></tr>').join('')+'</tbody></table></div></details><a class="download" id="download">Download original check report</a><details class="technical"><summary>File and processing details</summary><p class="mono">Recording: '+esc(r.digest)+'<br>Rules: '+esc(r.config_version)+'<br>Software: '+esc(r.code_version)+'</p></details>';
 let reviews=reviewData;
 function refreshReviewDownload(){
  const link=$('reviewDownload');link.hidden=!!reviews.error;
  if(!reviews.error){link.href=URL.createObjectURL(new Blob([JSON.stringify(reviews,null,2)],{type:'application/json'}));link.download=digest+'.reviews.json';}
  const previous=reviews.previous_report_reviews||[];
  $('previousReviewHistory').innerHTML=previous.length?'<details class="technical"><summary>Reviews from earlier evidence ('+previous.length+')</summary>'+previous.map(h=>'<p><strong>'+esc(reviewLabels[h.decision])+'</strong> · '+esc(Friendly.issues[h.finding.code]||h.finding.code)+' · '+esc(Friendly.stream(h.finding.stream))+'<br>'+esc(h.note||'No note')+'<br>'+esc(new Date(h.created_at).toLocaleString())+'</p>').join('')+'</details>':'';
  $('reviewNotice').textContent=reviews.error?'Human reviews could not load. Automatic results are still available.':reviews.previous_report_review_count?'Reviews from earlier processing or snapshot evidence are retained separately and are not applied to these findings.':'Human reviews are stored locally and do not replace the automatic result.';
 }
 function obstructionReviewPanels(){
  $('headReviews').innerHTML=reviews.issues.filter(item=>item.origin==='head_motion').map(item=>'<article class="finding"><strong>'+esc(Friendly.issues[item.finding.code]||'Head movement finding')+'</strong><p>'+esc(item.finding.why)+'</p>'+reviewPanel(item)+'</article>').join('');
  $('obstructionReviews').innerHTML=reviews.issues.filter(item=>item.origin==='snapshot_screen').map(item=>'<article class="finding"><strong>Possible blocked view · '+esc(Friendly.stream(item.finding.stream))+'</strong><p>'+Number(item.finding.start_s).toFixed(2)+'–'+Number(item.finding.end_s).toFixed(2)+' seconds</p>'+problemButton(item.finding.stream,item.finding.start_s,item.finding.end_s)+reviewPanel(item)+'</article>').join('');
 }
 refreshReviewDownload();obstructionReviewPanels();
 $('detailBody').onsubmit=async e=>{
  const form=e.target.closest('[data-review-id]');if(!form)return;e.preventDefault();
  const button=form.querySelector('button[type="submit"]'),status=form.querySelector('.review-status'),data=new FormData(form);
  button.disabled=true;status.textContent='Saving your review…';
  try{
   const updated=await api('/api/reviews/'+digest,{method:'POST',headers:{'Content-Type':'application/json','X-QC-Review':'1'},body:JSON.stringify({issue_id:form.dataset.reviewId,source_report_hash:reviews.source_report_hash,decision:data.get('decision'),note:data.get('note')})});
   if(sequence!==detailSequence||!$('detail').open)return;
   reviews=updated;const item=reviews.issues.find(i=>i.id===form.dataset.reviewId);
   form.outerHTML=reviewPanel(item);refreshReviewDownload();
  }catch(error){if(sequence===detailSequence&&$('detail').open){status.textContent=error.message;button.disabled=false;}}
 };
 function bindHead(current){
  if(!headMotionEnabled)return;
  const evidence=current.scorecard?.head_motion,link=$('headDownload');
  if(link&&evidence){link.href=URL.createObjectURL(new Blob([JSON.stringify(evidence,null,2)],{type:'application/json'}));link.download=digest+'.head-motion.json';}
  const button=$('checkHead');if(!button||!headScanningEnabled)return;
  button.onclick=async()=>{
   button.disabled=true;$('headStatus').textContent='Reading every head-pose message in this recording…';
   try{
    await api('/api/head-motion/'+digest,{method:'POST',headers:{'X-QC-Analysis':'1'}});
    const [updated,updatedReviews]=await Promise.all([api('/api/grades/'+digest+'?profile='+encodeURIComponent(activeProfile)),api('/api/reviews/'+digest)]);
    if(sequence!==detailSequence||!$('detail').open)return;
    reviews=updatedReviews;$('headPanel').innerHTML=HeadMotionUI.render(updated.scorecard.head_motion,headScanningEnabled);
    $('scorecard').innerHTML=gradingPanel(updated);$('timelinePanel').innerHTML=timelinePanel(r,updated.scorecard.obstruction,updated.scorecard.head_motion);
    bindHead(updated);bindScorecard(updated);obstructionReviewPanels();refreshReviewDownload();refresh();
   }catch(error){if(sequence===detailSequence&&$('headStatus')){$('headStatus').textContent=error.message;button.disabled=false;}}
  };
 }
 bindHead(g);
 function bindScorecard(current){
  const link=$('gradeDownload');link.href=URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));link.download=digest+'.grade.json';
  $('checkObstruction').onclick=async()=>{
   $('checkObstruction').disabled=true;$('obstructionStatus').textContent='Checking saved snapshots. This may take a minute…';
   try{
    await api('/api/obstruction/'+digest,{method:'POST',headers:{'X-QC-Analysis':'1'}});
    const updated=await api('/api/grades/'+digest+'?profile='+encodeURIComponent(activeProfile));
    if(sequence!==detailSequence||!$('detail').open)return;
    $('timelinePanel').innerHTML=timelinePanel(r,updated.scorecard?.obstruction,updated.scorecard?.head_motion);$('scorecard').innerHTML=gradingPanel(updated);bindScorecard(updated);refresh();
    reviews=await api('/api/reviews/'+digest);if(sequence===detailSequence&&$('detail').open){obstructionReviewPanels();refreshReviewDownload();}
   }catch(e){if(sequence===detailSequence&&$('obstructionStatus')){$('obstructionStatus').textContent=e.message;$('checkObstruction').disabled=false;}}
  };
 }
 bindScorecard(g);
 const initial=r.findings.find(f=>f.start_s!=null);
 $('sampleTime').value=initial?((initial.start_s+initial.end_s)/2).toFixed(2):0;
 let sampleSequence=0;
 async function loadImages(t,topic='',interval=null){
  if(!Number.isFinite(t)||t<0||t>86400)return;
  const request=++sampleSequence;
  const camera=r.streams.find(s=>s.kind==='video'&&s.topic===topic);
  $('sampleHeading').textContent=interval?(camera?'Problem images — '+Friendly.stream(topic):'Related images for this issue'):'Look at the recording';
  $('sampleTime').value=t.toFixed(3);
  $('loadSamples').disabled=true;$('sampleGrid').setAttribute('aria-busy','true');$('sampleGrid').textContent='Loading saved images…';
  $('sampleContext').textContent=interval?(camera?Friendly.stream(topic)+': ':'Related camera images for '+Friendly.stream(topic)+'. These do not show the sensor or file fault itself. ')+
   'Flagged interval: '+interval[0].toFixed(2)+'–'+interval[1].toFixed(2)+' seconds. Showing the nearest saved snapshot to '+t.toFixed(2)+' seconds.':'Showing saved images from all available cameras near '+t.toFixed(2)+' seconds.';
  try{
   const frames=await api('/api/samples/'+digest+'/'+t.toFixed(3));
   if(sequence!==detailSequence||request!==sampleSequence||!$('detail').open)return;
   const visible=camera?frames.filter(f=>f.topic===topic):frames;
   $('sampleGrid').innerHTML=visible.length?visible.map(f=>'<figure class="'+(camera?'affected-camera':'')+'"><img alt="'+esc(Friendly.stream(f.topic))+' at '+Number(f.seconds).toFixed(2)+' seconds" src="data:image/jpeg;base64,'+f.image+'"><figcaption><strong>'+esc(Friendly.stream(f.topic))+'</strong><br>Snapshot taken at '+Number(f.seconds).toFixed(2)+' seconds'+(interval&&(f.seconds<interval[0]||f.seconds>interval[1])?'<br><span class="snapshot-warning">This saved snapshot is outside the flagged interval. The issue may not be visible in this image.</span>':'')+'</figcaption></figure>').join(''):'No saved images are available for '+(camera?'this camera.':'this recording.');
  }catch(e){if(sequence===detailSequence&&request===sampleSequence&&$('detail').open)$('sampleGrid').textContent=e.message;}
  finally{if(sequence===detailSequence&&request===sampleSequence){$('loadSamples').disabled=false;$('sampleGrid').setAttribute('aria-busy','false');}}
 }
 $('loadSamples').onclick=()=>loadImages(Number($('sampleTime').value));
 $('detailBody').onclick=e=>{
  const button=e.target.closest('[data-problem-start]');if(!button)return;
  const start=Number(button.dataset.problemStart),end=Number(button.dataset.problemEnd);
  loadImages((start+end)/2,button.dataset.problemTopic,[start,end]);
  $('problemImages').scrollIntoView({block:'start'});
  $('sampleHeading').focus({preventScroll:true});
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
 'Scores of '+a+'/10 or higher meet the standard; '+r+' to below '+a+' need a check before use. Lower scores are below the standard. Findings needing review limit the Overall Score to 8. Serious issues limit it to 2 or 4 and prevent acceptance. Missing information leaves the score incomplete.';
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
async function initialize(){try{
 const features=await api('/api/features').catch(()=>({head_motion:false}));
 if(features.head_motion){
  await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/head-motion.js';script.onload=resolve;script.onerror=reject;document.head.append(script);});
  headMotionEnabled=true;headScanningEnabled=features.head_analysis;Object.assign(Friendly.issues,HeadMotionUI.names);
 }
 const data=await api('/api/profiles');profiles=data.profiles;activeProfile=data.default;profileOptions();await refresh();}catch(e){$('notice').textContent=e.message;}}
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
