(function(root){
'use strict';
const copy=v=>JSON.parse(JSON.stringify(v)),id=()=>`flow_${crypto.randomUUID().replaceAll('-','').slice(0,12)}`;
const seq=(items=[])=>({id:id(),type:'sequence',items});
const actionTypes=['tap','hold','move','scroll'];
function decode(n){
 if(!n||typeof n.id!=='string')throw Error('流程结构无效');
 if(n.type==='sequence')return {id:n.id,type:n.type,items:(n.items||[]).map(decode)};
 if(n.type==='parallel')return {id:n.id,type:n.type,branches:(n.branches||[]).map(decode),collapsed:!!n.collapsed};
 if(n.type==='repeat')return {id:n.id,type:n.type,body:decode(n.body),count:n.count,gap:n.gap_ms||0,collapsed:!!n.collapsed};
 if(n.type==='wait')return {id:n.id,type:n.type,duration:n.wait_ms||0};
 if(!actionTypes.includes(n.type)||!n.action)throw Error('未知动作类型');
 const b=n.action;
 return {id:n.id,type:n.type,duration:b.duration_ms,key:b.key,x:b.x,y:b.y,fromX:b.from_x??0,fromY:b.from_y??0,delta:b.delta,disabled:!!n.disabled,path:copy(b.path||[]),original:copy(b)};
}
function encode(n){
 const base={id:n.id,type:n.type};
 if(n.type==='sequence')return {...base,items:n.items.map(encode)};
 if(n.type==='parallel')return {...base,branches:n.branches.map(encode),collapsed:!!n.collapsed};
 if(n.type==='repeat')return {...base,body:encode(n.body),count:n.count,gap_ms:n.gap,collapsed:!!n.collapsed};
 if(n.type==='wait')return {...base,wait_ms:n.duration};
 const b={...(n.original||{}),id:n.id,type:n.type,at_ms:0,duration_ms:n.duration};
 if(n.type==='tap'||n.type==='hold')b.key=n.key;
 if(n.type==='move'){b.x=n.x;b.y=n.y;b.from_x=n.fromX;b.from_y=n.fromY;if(n.path?.length)b.path=copy(n.path);else delete b.path;}
 if(n.type==='scroll')b.delta=n.delta;
 return {...base,action:b,disabled:!!n.disabled};
}
function duration(n){if(n.type==='sequence')return n.items.reduce((sum,item)=>sum+duration(item),0);if(n.type==='parallel')return Math.max(0,...n.branches.map(duration));if(n.type==='repeat')return duration(n.body)*n.count+n.gap*(n.count-1);return n.duration;}
function fromLegacy(raw){
 const m=copy(raw),source=m.graph?copy(m.graph):null;
 if(m.graph){if(m.graph.version!==1)throw Error('不支持此流程版本');root.GraphModel.materialize(m);}else root.TimelineModel.syncTiming(m);
 const split=root.TimelineModel.splitTracks(m),lanes=[];
 for(const t of split.tracks){let at=0;const items=[];for(const b of [...t.blocks].sort((a,b)=>a.at_ms-b.at_ms)){if(b.at_ms>at)items.push({id:id(),type:'wait',duration:b.at_ms-at});items.push(decode({id:b.id,type:b.type,action:b,disabled:!!t.muted}));at=b.at_ms+b.duration_ms;}if(items.length)lanes.push(seq(items));}
 const body=lanes.length>1?seq([{id:id(),type:'parallel',branches:lanes,collapsed:false}]):lanes[0]||seq();
 const expected=Math.max(0,m.duration_ms-(m.loop?(m.loop_wait_ms||0):0));const tail=expected-duration(body);if(tail>0)body.items.push({id:id(),type:'wait',duration:tail});
 return {...macroBase(m),body,sourceV1:source};
}
function macroBase(m){return {id:m.id,name:m.name,trigger:m.trigger||'none',enabled:m.enabled!==false,mode:m.loop?'continuous':'once',gap:m.loop_wait_ms||0};}
function fromMacro(m){if(m.graph?.version===2)return {...macroBase(m),body:decode(m.graph.root),sourceV1:m.graph.source_v1?copy(m.graph.source_v1):null};return fromLegacy(m);}
function toMacro(m){return {id:m.id,name:m.name,trigger:m.trigger,enabled:m.enabled!==false,loop:m.mode==='continuous',loop_wait_ms:m.gap,duration_ms:Math.max(1,duration(m.body)+(m.mode==='continuous'?m.gap:0)),tracks:[],graph:{version:2,root:encode(m.body),...(m.sourceV1?{source_v1:copy(m.sourceV1)}:{})}};}
function expand(body,limit=100000){
 const stats=new Map(),seen=new Set();
 function measure(n,depth=0){
  if(!n||!n.id||seen.has(n.id)||seen.size>=4096||depth>32)throw Error('节点 ID 重复、节点过多或嵌套过深');seen.add(n.id);
  let result={duration:0,actions:0,events:0};
  if(n.type==='sequence'||n.type==='parallel'||n.type==='repeat'){
   if(n.type==='parallel'&&(n.branches.length<1||n.branches.length>64))throw Error('同时执行框支持 1–64 条分支');
   if(n.type==='repeat'&&(!Number.isSafeInteger(n.count)||n.count<1||n.count>100||!Number.isSafeInteger(n.gap)||n.gap<0||n.gap>3600000))throw Error('重复次数须为 1–100，间隔须在 0ms–1 小时内');
   const children=n.type==='sequence'?n.items:n.type==='parallel'?n.branches:[n.body];
   for(const child of children){if((n.type==='parallel'||n.type==='repeat')&&child?.type!=='sequence')throw Error('范围内容必须是顺序');const s=measure(child,depth+1);result.duration=n.type==='parallel'?Math.max(result.duration,s.duration):result.duration+s.duration;result.actions+=s.actions;result.events+=s.events;}
   if(n.type==='repeat'){result.duration=result.duration*n.count+n.gap*(n.count-1);result.actions*=n.count;result.events*=n.count;}
  }else{
   if(!['wait',...actionTypes].includes(n.type)||!Number.isSafeInteger(n.duration)||n.duration<0||n.duration>3600000)throw Error('动作类型或时长无效');result.duration=n.duration;
   if(n.type!=='wait'){result.actions=1;result.events=n.disabled?0:n.type==='tap'||n.type==='hold'?2:n.type==='scroll'?1:n.path?.length|| (n.duration===0?1:Math.max(1,Math.ceil(n.duration/8))+1);}
  }
  if(!Number.isSafeInteger(result.duration)||result.duration>3600000||result.actions>limit||result.events>limit)throw Error('流程超过 1 小时或展开后的动作/事件超过 100000 个');stats.set(n,result);return result;
 }
 const total=measure(body),events=[];
 function emit(n,at,loops=[]){const s=stats.get(n);if(n.type==='wait'){events.push({id:n.id,at,end:at+n.duration,loops,disabled:false,type:n.type});return;}
  if(n.type==='sequence'){for(const child of n.items){emit(child,at,loops);at+=stats.get(child).duration;}}
  else if(n.type==='parallel'){for(const branch of n.branches)emit(branch,at,loops);}
  else if(n.type==='repeat'){if(s.actions===0){events.push({id:n.id,at,end:at+s.duration,loops,disabled:true,type:'wait'});return;}for(let i=0;i<n.count;i++)emit(n.body,at+i*(stats.get(n.body).duration+n.gap),[...loops,{id:n.id,iteration:i+1,count:n.count}]);}
  else events.push({id:n.id,at,end:at+s.duration,loops,disabled:!!n.disabled,type:n.type});
  if(events.length>limit+4096)throw Error('预览动作过多');
 }
 emit(body,0);events.sort((a,b)=>a.at-b.at);return {duration:total.duration,events,stats};
}
root.FlowModel={decode,encode,duration,fromMacro,toMacro,expand,fromLegacy};
})(typeof window==='undefined'?globalThis:window);
