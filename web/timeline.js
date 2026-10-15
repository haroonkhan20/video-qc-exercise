/* Presentation of existing findings only; no new detections or score changes. */
const IssueTimeline=(()=>{
 function model(report,obstruction){
  const inventory=report.inventory||{};
  const duration=(inventory.end_ns-inventory.start_ns)/1e9;
  const validDuration=Number.isFinite(inventory.start_ns)&&Number.isFinite(inventory.end_ns)&&Number.isFinite(duration)&&duration>0;
  const findings=[...(report.findings||[])];
  for(const stream of obstruction?.streams||[])for(const run of stream.runs||[])
   findings.push({code:'POSSIBLE_OBSTRUCTION',stream:stream.topic,start_s:run.start_s,end_s:run.end_s});
  const groups=new Map(),untimed=[],seen=new Set();
  for(const finding of findings){
   const {code,stream='',start_s:start,end_s:end}=finding;
   const key=JSON.stringify([code,stream,start,end]);if(seen.has(key))continue;seen.add(key);
   if(!validDuration||!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<start||end===0||start>duration){untimed.push(finding);continue;}
   const item={code,stream,start,end:Math.min(end,duration)};
   const groupKey=JSON.stringify([code,stream]);
   if(!groups.has(groupKey))groups.set(groupKey,{code,stream,items:[],lanes:[]});
   groups.get(groupKey).items.push(item);
  }
  for(const group of groups.values()){
   const ends=[];
   for(const item of group.items.sort((a,b)=>a.start-b.start||a.end-b.end)){
    const left=Math.min(item.start/duration,.985),width=Math.max((item.end-item.start)/duration,.015);
    let lane=ends.findIndex(end=>end<=left);
    if(lane<0){lane=ends.length;group.lanes.push([]);}
    ends[lane]=left+width;group.lanes[lane].push({...item,left:left*100,width:Math.min(width,1-left)*100});
   }
  }
  return {duration:validDuration?duration:null,groups:[...groups.values()],untimed,
          obstructionChecked:obstruction?.status==='checked'};
 }
 return {model};
})();
if(typeof module!=='undefined')module.exports=IssueTimeline;
