(function(root){
'use strict';
const M=root.TimelineModel, clone=v=>structuredClone(v);
const types={start:{name:'开始',icon:'▷',color:'mint',hint:'快捷键触发整段流程'},tap:{name:'点击按键',icon:'⌁',color:'blue',hint:'按下后自动抬起'},hold:{name:'按住按键',icon:'━',color:'blue',hint:'持续按住，再自动抬起'},wait:{name:'等待',icon:'◷',color:'amber',hint:'暂停一段时间，再继续'},move:{name:'鼠标移动',icon:'↗',color:'purple',hint:'移动到屏幕位置'},scroll:{name:'鼠标滚轮',icon:'↕',color:'purple',hint:'向上或向下滚动'},parallel:{name:'并行',icon:'⑂',color:'mint',hint:'同时开始多条分支'},join:{name:'汇合',icon:'⑃',color:'mint',hint:'等待所有分支结束再继续'}};
const actionTypes=['tap','hold','move','scroll'];
function node(type,x=0,y=0){if(!types[type])throw Error('未知节点类型');const n={id:M.id('node'),type,x,y};if(actionTypes.includes(type))n.action=M.block(type);if(type==='wait')n.wait_ms=500;return n;}
function empty(){return {version:1,nodes:[node('start',80,180)],edges:[]};}
function macro(name='新流程'){return {...M.macro(name),graph:empty()};}
function schedule(g){
 if(g.version!==1||!g.nodes.length||g.nodes.length>4096||g.edges.length>8192)throw Error('节点图格式无效或超过 4096 个节点');
 const nodes=new Map(),incoming=new Map(),outgoing=new Map();let start;
 for(const n of g.nodes){if(!n.id||n.id.length>128||nodes.has(n.id)||!Number.isFinite(n.x)||!Number.isFinite(n.y)||Math.abs(n.x)>1000000||Math.abs(n.y)>1000000)throw Error('节点 ID 或位置无效');if(!types[n.type])throw Error('未知节点类型');if(n.type==='start'){if(start)throw Error('只能有一个开始节点');start=n.id;}if(n.type==='wait'&&(!Number.isSafeInteger(n.wait_ms)||n.wait_ms<0||n.wait_ms>M.maxDuration))throw Error('等待时间必须在 0ms–1 小时内');if(actionTypes.includes(n.type)&&(!n.action||n.action.type!==n.type||!Number.isSafeInteger(n.action.duration_ms)||n.action.duration_ms<0||n.action.duration_ms>M.maxDuration))throw Error('动作节点参数无效');nodes.set(n.id,n);incoming.set(n.id,[]);outgoing.set(n.id,[]);}
 if(!start)throw Error('缺少开始节点');const seen=new Set();
 for(const e of g.edges){const key=JSON.stringify([e.from,e.to]);if(!nodes.has(e.from)||!nodes.has(e.to)||e.from===e.to||seen.has(key))throw Error('连线无效或重复');seen.add(key);incoming.get(e.to).push(e.from);outgoing.get(e.from).push(e.to);}
 const degrees=new Map(),queue=[];
 for(const n of g.nodes){const a=incoming.get(n.id).length,b=outgoing.get(n.id).length;if(n.type==='start'&&a||n.type!=='join'&&a>1||n.type!=='parallel'&&b>1||a>64||b>64)throw Error('多路输出请使用并行节点，多路输入请使用汇合节点');degrees.set(n.id,a);if(!a)queue.push(n.id);}
 const times=new Map(),order=[];let duration=0;
 while(queue.length){const id=queue.shift(),n=nodes.get(id),parents=incoming.get(id),active=id===start||parents.some(p=>times.get(p).active);let at=0;for(const p of parents)at=Math.max(at,times.get(p).end);if(active&&parents.some(p=>!times.get(p).active))throw Error('汇合分支尚未连接开始节点');const span=n.type==='wait'?n.wait_ms:actionTypes.includes(n.type)?n.action.duration_ms:0,end=active?at+span:0;if(end>M.maxDuration)throw Error('流程总时长不能超过 1 小时');times.set(id,{at:active?at:0,end,active});if(active)duration=Math.max(duration,end);order.push(id);for(const child of outgoing.get(id)){degrees.set(child,degrees.get(child)-1);if(!degrees.get(child))queue.push(child);}}
 if(order.length!==g.nodes.length)throw Error('不能连接成环；重复执行请开启宏循环');
 return {times,order,duration,incoming,outgoing,nodes};
}
function materialize(m){
 const s=schedule(m.graph),tracks=[],ends=[];
 const actions=m.graph.nodes.filter(n=>actionTypes.includes(n.type)&&s.times.get(n.id).active).sort((a,b)=>s.times.get(a.id).at-s.times.get(b.id).at);
 for(const n of actions){const b={...clone(n.action),id:n.id,at_ms:s.times.get(n.id).at};let lane=ends.findIndex((end,i)=>end<=b.at_ms&&tracks[i].muted===!!n.muted);if(lane<0){if(tracks.length>=64)throw Error('同时执行的动作超过 64 路');lane=tracks.length;tracks.push({id:`graph_track_${lane}`,name:`流程 ${lane+1}`,muted:!!n.muted,blocks:[]});ends.push(0);}tracks[lane].blocks.push(b);ends[lane]=M.occupiedEnd(b);}
 const wait=m.loop_wait_ms||0;if(!Number.isSafeInteger(wait)||wait<0||wait>M.maxDuration||m.loop&&s.duration+wait>M.maxDuration)throw Error('每轮等待或流程总时长超出范围');
 m.tracks=tracks;m.duration_ms=Math.max(1,s.duration+(m.loop?wait:0));return s;
}
function connect(g,from,to){const next=clone(g);next.edges.push({from,to});schedule(next);g.edges=next.edges;}
function add(g,type,after,position){
 if(type==='start')throw Error('每个流程只需要一个开始节点');const parent=g.nodes.find(n=>n.id===after),n=node(type,position?.x??(parent?parent.x+280:100),position?.y??(parent?parent.y:100));const next=clone(g);next.nodes.push(n);
 if(parent){const edges=next.edges.filter(e=>e.from===parent.id);if(parent.type==='parallel'){n.y=parent.y+edges.length*200;next.edges.push({from:parent.id,to:n.id});}else{const descendants=new Set(),queue=edges.map(e=>e.to);while(queue.length){const id=queue.shift();if(descendants.has(id))continue;descendants.add(id);queue.push(...next.edges.filter(e=>e.from===id).map(e=>e.to));}for(const old of next.nodes)if(descendants.has(old.id)&&old.x>=n.x-40)old.x+=280;next.edges=next.edges.filter(e=>e.from!==parent.id);next.edges.push({from:parent.id,to:n.id});for(const e of edges)next.edges.push({from:n.id,to:e.to});}}
 schedule(next);g.nodes=next.nodes;g.edges=next.edges;return n;
}
function remove(g,id){const n=g.nodes.find(n=>n.id===id);if(!n||n.type==='start')return;const ins=g.edges.filter(e=>e.to===id),outs=g.edges.filter(e=>e.from===id);g.nodes=g.nodes.filter(n=>n.id!==id);g.edges=g.edges.filter(e=>e.to!==id&&e.from!==id);if(ins.length===1&&outs.length===1){try{connect(g,ins[0].from,outs[0].to);}catch{ /* Removing a node may leave its branch disconnected. */ }} }
function duplicate(g,id){const source=g.nodes.find(n=>n.id===id);if(!source||source.type==='start')return null;const n=clone(source);n.id=M.id('node');n.x+=40;n.y+=190;g.nodes.push(n);return n;}
function layout(g){const s=schedule(g),depth=new Map(),rows=new Map();for(const id of s.order){const n=s.nodes.get(id),d=Math.max(0,...s.incoming.get(id).map(p=>(depth.get(p)||0)+1));depth.set(id,d);const row=rows.get(d)||0;n.x=80+d*280;n.y=100+row*210;rows.set(d,row+1);}}
function fromTimeline(m){
 if(m.graph){materialize(m);return m;}
 M.syncTiming(m);const split=M.splitTracks(m),g=empty(),start=g.nodes[0];start.y=100;let rootID=start.id;
 if(split.tracks.length>1){const fork=node('parallel',360,100);g.nodes.push(fork);g.edges.push({from:start.id,to:fork.id});rootID=fork.id;}
 split.tracks.forEach((t,row)=>{let parent=rootID,end=0,col=split.tracks.length>1?2:1;for(const b of [...t.blocks].sort((a,b)=>a.at_ms-b.at_ms)){const gap=b.at_ms-end;if(gap>0){const w=node('wait',80+col++*280,100+row*210);w.wait_ms=gap;g.nodes.push(w);g.edges.push({from:parent,to:w.id});parent=w.id;}const n=node(b.type,80+col++*280,100+row*210);n.action=clone(b);n.muted=!!t.muted;g.nodes.push(n);g.edges.push({from:parent,to:n.id});parent=n.id;end=M.extent(b);}});
 m.graph=g;materialize(m);return m;
}
function demo(){const m=macro('技能连招');m.trigger='f1';const g=m.graph;let id=g.nodes[0].id;for(const type of ['tap','wait','hold']){const n=add(g,type,id);if(type==='tap')n.action.key='1';if(type==='wait')n.wait_ms=300;if(type==='hold'){n.action.key='right';n.action.duration_ms=800;}id=n.id;}materialize(m);return {...M.settings,macros:[m]};}
root.GraphModel={types,actionTypes,node,empty,macro,schedule,materialize,connect,add,remove,duplicate,layout,fromTimeline,demo};
})(typeof window==='undefined'?globalThis:window);
