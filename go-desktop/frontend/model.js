// Authoring state and geometry are independent of DOM, Wails and execution.
(function(root){
'use strict';
const id=prefix=>`${prefix}_${crypto.randomUUID().replaceAll('-','').slice(0,12)}`;
const settings={schema_version:3,window_title_contains:'暗黑破坏神IV',process_name:'Diablo IV.exe',overlay_enabled:true,overlay_opacity:.6,overlay_avoid_mouse:true,overlay_avoid_distance:72,recording_trigger:'f12',recording_countdown_sec:3,recording_max_seconds:60,emergency_trigger:'pause'};
const actionTypes=new Set(['tap','hold','move','scroll']);
const maxDuration=3600000;
function block(type,at=0){if(!actionTypes.has(type))throw Error(`未知动作 ${type}`);return {id:id('block'),type,at_ms:at,duration_ms:type==='tap'?60:type==='hold'?600:type==='move'?300:0,...(['tap','hold'].includes(type)?{key:type==='hold'?'right':'2'}:{}),...(type==='move'?{x:800,y:500,from_x:400,from_y:500}:{}),...(type==='scroll'?{delta:-120}:{})};}
const track=(name='新轨道')=>({id:id('track'),name,muted:false,blocks:[]});
const macro=(name='未命名宏')=>({id:id('macro'),name,enabled:true,trigger:'none',duration_ms:1,loop:false,loop_wait_ms:0,tracks:[track('轨道 1')]});
function demo(){const m=macro('我的第一个宏');m.trigger='f1';m.tracks[0].name='技能';m.tracks[0].blocks=[{...block('tap',200),key:'2'},{...block('tap',800),key:'1'}];m.tracks.push({...track('鼠标'),blocks:[{...block('hold',200),duration_ms:1200,key:'right'}]});syncTiming(m);return {...settings,macros:[m]};}
function snap(ms,grid=10){return Math.max(0,Math.round(ms/grid)*grid);}
function find(m,id){for(const t of m.tracks){const b=t.blocks.find(b=>b.id===id);if(b)return {track:t,block:b};}return null;}
function extent(b){return b.at_ms+(b.duration_ms||0);}
function occupiedEnd(b){return b.at_ms+Math.max(1,b.duration_ms||0);}
function overlaps(a,b){return a.at_ms<occupiedEnd(b)&&b.at_ms<occupiedEnd(a);}
function conflict(t,b,ignore=b.id){return t.blocks.find(other=>other.id!==ignore&&overlaps(b,other));}
function trackOverlaps(t){const blocks=[...t.blocks].sort((a,b)=>a.at_ms-b.at_ms);return blocks.some((b,i)=>i>0&&b.at_ms<occupiedEnd(blocks[i-1]));}
function ensureTiming(b){if(!Number.isSafeInteger(b.at_ms)||!Number.isSafeInteger(b.duration_ms)||b.at_ms<0||b.duration_ms<0||extent(b)>maxDuration)throw Error('动作时间必须在 0ms–1 小时内。');}
function ensurePlacement(t,b){ensureTiming(b);if(conflict(t,b))throw Error('同一轨道不能重叠，请放到空白处或另一条轨道。');}
function actionDuration(m){return m.tracks.reduce((end,t)=>t.blocks.reduce((end,b)=>Math.max(end,extent(b)),end),0);}
function ensureWait(m,wait,end=actionDuration(m)){if(!Number.isSafeInteger(wait)||wait<0||wait>maxDuration)throw Error('每轮结束后等待应为 0ms–1 小时。');if(m.loop&&end+wait>maxDuration)throw Error('动作时长与每轮等待之和不能超过 1 小时。');}
function syncTiming(m){for(const t of m.tracks)for(const b of t.blocks)ensureTiming(b);const end=actionDuration(m);if(m.loop_wait_ms===undefined)m.loop_wait_ms=m.loop?Math.max(0,(m.duration_ms||0)-end):0;ensureWait(m,m.loop_wait_ms,end);m.duration_ms=Math.max(1,end+(m.loop?m.loop_wait_ms:0));return m.duration_ms;}
function setLoopWait(m,wait){ensureWait(m,wait);m.loop_wait_ms=wait;return syncTiming(m);}
function place(m,type,trackID,at,grid=10){const t=m.tracks.find(t=>t.id===trackID);if(!t)throw Error('找不到目标轨道');const b=block(type,snap(at,grid));ensurePlacement(t,b);ensureWait(m,m.loop_wait_ms||0,extent(b));t.blocks.push(b);syncTiming(m);return b;}
function move(m,blockID,trackID,at,grid=10){const found=find(m,blockID),target=m.tracks.find(t=>t.id===trackID);if(!found||!target)return;const next={...found.block,at_ms:snap(at,grid)};ensurePlacement(target,next);ensureWait(m,m.loop_wait_ms||0,extent(next));found.track.blocks=found.track.blocks.filter(b=>b.id!==blockID);found.block.at_ms=next.at_ms;target.blocks.push(found.block);syncTiming(m);}
function resizeDuration(m,blockID,duration,grid=10){const f=find(m,blockID);if(!f)return 0;const b=f.block;let next=Math.max(b.type==='move'?0:1,snap(duration,grid));for(const other of f.track.blocks){if(other.id!==b.id&&other.at_ms>=b.at_ms)next=Math.min(next,other.at_ms-b.at_ms);}if(next<(b.type==='move'?0:1))throw Error('动作之间没有足够空间，请移到另一条轨道。');ensureTiming({...b,duration_ms:next});return next;}
function resize(m,blockID,duration,grid=10){const f=find(m,blockID);if(!f)return;const next=resizeDuration(m,blockID,duration,grid);ensurePlacement(f.track,{...f.block,duration_ms:next});ensureWait(m,m.loop_wait_ms||0,f.block.at_ms+next);if(f.block.path?.length){const old=Math.max(1,f.block.duration_ms);for(const p of f.block.path)p.at_ms=Math.round(p.at_ms*next/old);}f.block.duration_ms=next;syncTiming(m);return next;}
function cloneBlock(m,blockID){const f=find(m,blockID);if(!f)return null;const b=structuredClone(f.block);b.id=id('block');b.at_ms=extent(b)+50;for(const other of [...f.track.blocks].sort((a,b)=>a.at_ms-b.at_ms)){if(overlaps(b,other))b.at_ms=occupiedEnd(other);}ensurePlacement(f.track,b);ensureWait(m,m.loop_wait_ms||0,extent(b));f.track.blocks.push(b);syncTiming(m);return b;}
function splitTracks(m){
 const tracks=[];
 for(const t of m.tracks){
  if(!trackOverlaps(t)){tracks.push(t);continue;}
  const lanes=[],ends=[];
  for(const b of [...t.blocks].sort((a,b)=>a.at_ms-b.at_ms)){
   let index=ends.findIndex(end=>b.at_ms>=end);
   if(index<0){index=lanes.length;lanes.push({...t,id:index?id('track'):t.id,name:index?`${t.name} · ${index+1}`:t.name,blocks:[]});ends.push(-1);}
   lanes[index].blocks.push(b);ends[index]=occupiedEnd(b);
  }
  tracks.push(...lanes);
 }
 if(tracks.length>64)throw Error('拆分后超过 64 条轨道，请减少同时发生的动作。');
 return {...m,tracks};
}
function errors(m){const issues=[];if(!m.name.trim())issues.push('给这个宏起一个名字');try{ensureWait(m,m.loop_wait_ms||0);}catch(e){issues.push(e.message);}let count=0;
for(const t of m.tracks){if(trackOverlaps(t))issues.push(`轨道“${t.name}”中有重叠动作，请拆分到不同轨道`);for(const b of t.blocks){if(!actionTypes.has(b.type)){issues.push(`未知动作 ${b.type}`);continue;}if(t.muted)continue;count++;if(b.at_ms<0||extent(b)>m.duration_ms)issues.push('有动作超出了时间轴');if(['tap','hold'].includes(b.type)&&b.duration_ms<1)issues.push('点击和按住至少持续 1ms');}}
if(count===0)issues.push('从左侧拖入第一个动作');return [...new Set(issues)];}
function flatten(m){const events=[];for(const t of m.tracks){if(trackOverlaps(t))throw Error(`轨道“${t.name}”中有重叠动作，请拆分到不同轨道`);for(const b of t.blocks){if(!actionTypes.has(b.type))throw Error(`未知动作 ${b.type}`);if(t.muted)continue;if(events.length>100000)throw Error('动作过多');if(['tap','hold'].includes(b.type)){events.push({at_ms:b.at_ms,type:'key_down',key:b.key,block:b.id},{at_ms:b.at_ms+b.duration_ms,type:'key_up',key:b.key,block:b.id});}else events.push({at_ms:b.at_ms,type:b.type,key:b.key,x:b.x,y:b.y,block:b.id});}}const priority={key_up:0,move:1,key_down:2,scroll:3};return events.sort((a,b)=>a.at_ms-b.at_ms||priority[a.type]-priority[b.type]);}
root.TimelineModel={id,settings,block,track,macro,demo,snap,find,extent,occupiedEnd,overlaps,conflict,trackOverlaps,place,move,resizeDuration,resize,cloneBlock,splitTracks,actionDuration,syncTiming,setLoopWait,errors,flatten,maxDuration};
})(typeof window==='undefined'?globalThis:window);
