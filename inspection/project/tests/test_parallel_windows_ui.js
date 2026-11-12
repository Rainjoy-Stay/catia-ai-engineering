'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../tools/dashboard.js'),'utf8');
const nodes={};
function node(){return {textContent:'',value:'',checked:false,classList:{add(){},remove(){}},append(){},remove(){},setAttribute(){},addEventListener(){}}}
const context={lanes:[],data:{},parallelModuleHidden:false,state:{status:'RUNNING',resident:{workers:12}},lastFollow:'',
 $:id=>nodes[id]||(nodes[id]=node()),txt:()=>node(),document:{createElement:()=>node()},
 short:x=>x,identity:x=>x,choose(){},View:class {constructor(){this.events={abort(){}}}fit(){}}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function makeLanes('),source.indexOf('async function loadPreview(')),context);
const active=n=>Array.from({length:n},(_,i)=>({stage:'EXACT_PAIR_PRIMARY_START',index:i,object_a:'A'+i,object_b:'B'+i}));
context.$('showParallel').checked=true;context.$('windowCount').value='auto';
context.data.active_pairs=active(12);context.updateLanes();assert.equal(context.lanes.length,12);
assert.equal(context.lanes.filter(l=>l.event).length,12);assert.equal(nodes.workers.value,12);
const retained=context.lanes[0].view;context.updateLanes();assert.equal(context.lanes[0].view,retained);
context.data.active_pairs=active(8);context.updateLanes();assert.equal(context.lanes.length,8);assert.equal(context.lanes[0].view,retained);
context.data.active_pairs=active(16);context.updateLanes();assert.equal(context.lanes.length,16);
nodes.windowCount.value='4';context.updateLanes();assert.equal(context.lanes.length,4);assert.equal(nodes.activeCount.textContent,16);
nodes.showParallel.checked=false;context.updateLanes();assert.equal(context.lanes.length,0);assert.equal(nodes.lanes.hidden,true);assert.equal(nodes.windowCount.disabled,true);
nodes.showParallel.checked=true;nodes.windowCount.value='12';context.updateLanes();assert.equal(context.lanes.length,12);
context.parallelModuleHidden=true;context.updateLanes();assert.equal(context.lanes.length,0);context.parallelModuleHidden=false;
context.data.active_pairs=[];context.updateLanes();assert.equal(context.lanes.length,0);
console.log('Parallel windows: 12 / 8 / 16 / 0, retained views and worker sync passed');
