/* Presentation only. Original evidence, grades and saved standards are unchanged. */
const Friendly = (() => {
 const areas={integrity:'File condition',inventory:'Cameras and sensors',decoding:'Playable video',timing:'Smooth recording',alignment:'Recording alignment',image:'Picture quality',sensor:'Sensor readings'};
 const issues={BLACK_RUN:'BLACK_RUN — Very dark images',BRIGHT_RUN:'Very bright images',FROZEN_RUN:'Images hardly changed',BLUR_RUN:'Blurred images',SENSOR_FLATLINE:'Gripper reading stayed the same',UNEXPECTED_STREAM:'Extra camera or sensor data',GAP_RUN:'Recording interruptions',COVERAGE_MISMATCH:'Missing beginning or ending',CHECK_UNAVAILABLE:'A check could not finish',CONTAINER_UNREADABLE:'File cannot be read',CONTAINER_INCOMPLETE:'File information is incomplete',CONTAINER_TRUNCATED_RECOVERABLE:'File ends unexpectedly',MISSING_STREAM:'Required camera or sensor is missing',WRONG_SCHEMA:'Data is in an unexpected format',WRONG_ENCODING:'Data cannot be interpreted',VIDEO_UNDECODABLE:'Some video cannot be played',VIDEO_NOT_KEYFRAME_START:'Video starts without a complete picture',RESOLUTION_CHANGE:'Picture size changed',SENSOR_NONFINITE:'Invalid sensor readings',TIMESTAMP_DUPLICATE:'Repeated recording times',TIMESTAMP_REVERSED:'Recording times go backwards',PAYLOAD_TIMESTAMP_MISMATCH:'Recorded times do not agree',RATE_OUT_OF_RANGE:'Recording speed differs from expected',CAMERA_SYNC:'Camera times do not line up',MISSING_OR_INVALID_REQUIRED_STREAM:'Required camera or sensor is missing or invalid'};
 const number=v=>Number(v).toLocaleString(undefined,{maximumFractionDigits:3});
 const percent=v=>number(v*100)+'%';
 function stream(topic){
  const names={'/quest3s/head_left/camera/compressed':'Head camera · left','/quest3s/head_right/camera/compressed':'Head camera · right','/gripper/left/camera0/compressed':'Gripper camera · left','/gripper/right/camera0/compressed':'Gripper camera · right','/gripper/left/magnetic_encoder':'Gripper sensor · left','/gripper/right/magnetic_encoder':'Gripper sensor · right','/quest3s/head_pose':'Head movement','/quest3s/body_tracking':'Body movement','/quest3s/left_controller_pose':'Left controller movement','/quest3s/right_controller_pose':'Right controller movement','/quest3s/left_gripper_pose':'Left gripper movement','/quest3s/right_gripper_pose':'Right gripper movement'};
  if(names[topic])return names[topic];
  if(topic.includes('camera_info'))return topic.includes('head_left')?'Head camera settings · left':topic.includes('head_right')?'Head camera settings · right':topic.includes('/left/')?'Gripper camera settings · left':'Gripper camera settings · right';
  return topic==='Recording'?'Whole recording':topic||'Whole recording';
 }
 function parameter(p){
  return ({'Container completeness':'Can the file be read completely?','Required inventory':'Is the required camera or sensor present?','Decode discrepancy':'Can all video pictures be played?','Initial keyframe':'Does the video start with a complete picture?','Resolution consistency':'Does the picture size stay the same?','Union of image defects':'Total time with picture problems','Long-gap duration':'Time with recording interruptions','estimated_dropped_frames':'Estimated missing readings','timestamp_duplicate':'Repeated recording times','timestamp_reversed':'Recording times going backwards','Rate deviation':'Difference from the expected recording speed','Payload timestamp offset':'Do recorded times agree?','start_lag_s':'How late does this camera or sensor start?','end_lag_s':'How early does it stop?','skew_max_ms':'Difference between camera times','drift_ms':'Change in camera timing over the recording','Finite numeric values':'Are sensor readings valid?','Encoder stillness':'Time the gripper reading stayed the same','Evidence availability':'Was there enough information to check?','Timing evidence':'Was there enough timing information?'}[p.parameter]||issues[p.parameter]||p.parameter);
 }
 function why(p){
  if(!p.applicable)return 'This check does not apply to this kind of sensor.';
  if(p.score==null)return 'The check did not provide enough information to give a reliable mark.';
  const m=p.measured;
  if(m&&typeof m==='object'&&m.affected_seconds!=null&&m.duration_seconds>0){
   const text=number(m.affected_seconds)+' seconds out of '+number(m.duration_seconds)+' seconds ('+percent(m.affected_seconds/m.duration_seconds)+')';
   if(p.parameter==='Encoder stillness')return text+' with an unchanged reading. '+(p.why.includes('advisory')?'This standard does not lower the score for stillness.':'This standard lowers the score for stillness.');
   return text+' affected. This standard gives '+number(p.score)+'/10 for that amount.';
  }
  if(m&&typeof m==='object'&&m.count!=null)return number(m.count)+' '+(p.parameter==='estimated_dropped_frames'?'estimated missing readings':'timing errors')+' among '+number(m.messages)+' recorded readings. '+(p.parameter==='estimated_dropped_frames'?'This is a timing estimate, not confirmed data loss.':'The same problem is not counted twice for different clocks.');
  if(typeof m==='number'&&p.limit!=null){
   if(p.parameter==='Rate deviation')return 'Recording speed differs by '+percent(m)+'. Your allowance is '+percent(p.limit)+'.';
   const seconds=['Payload timestamp offset','skew_max_ms','drift_ms'].includes(p.parameter)?0.001:1;
   return 'Measured difference: '+number(Math.abs(m)*seconds)+' seconds. Your allowance: '+number(p.limit*seconds)+' seconds.';
  }
  if(p.parameter==='Decode discrepancy'&&typeof m==='number')return percent(m)+' difference between recorded and playable pictures, or reported playback errors. This is a check estimate.';
  if(p.score===10)return 'No problem was found by this check under this standard.';
  if(p.parameter==='Finite numeric values')return 'Some sensor readings are invalid and cannot be used reliably.';
  if(p.parameter==='Required inventory')return 'The required camera or sensor is missing or uses an unexpected data format.';
  if(p.parameter==='Container completeness')return 'The file could not be confirmed complete. See the issues below.';
  return 'This check found a problem. See the affected moments below or open technical details for the measurements.';
 }
 function category(c){
  if(c.score==null)return 'There is not enough information to score this area.';
  if(c.score===10)return 'No score-lowering problem was found in this area under this standard.';
  const s=c.streams.find(x=>x.topic===c.worst_stream);
  const p=s?.parameters.filter(p=>p.applicable&&p.score!=null).sort((a,b)=>a.score-b.score)[0];
  return p?stream(s.topic)+': '+why(p):'Problems in this area lowered the score.';
 }
 return {areas,issues,stream,parameter,why,category,number,percent};
})();
if(typeof module!=='undefined')module.exports=Friendly;
