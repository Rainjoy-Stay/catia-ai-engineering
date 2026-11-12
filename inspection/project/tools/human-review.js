// Human decisions are saved independently; no inspection verdict is rewritten.
(async function initHumanReview(){
 let round;
 try{const response=await fetch(base+'/human-review');if(!response.ok)return;round=await response.json();}catch{return;}
 const style=document.createElement('style');style.textContent=`
 #humanReview{grid-column:1/-1;padding:22px;background:#101e30;border:1px solid #486681;border-radius:16px;margin-bottom:18px;color:#e7eff8}
 #humanReview h2{margin:0 0 8px}#humanReview button{cursor:pointer}#humanReview .hrTabs,#humanReview .hrTools{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
 #humanReview button[aria-pressed=true]{background:#246794;border-color:#69c5ff;color:white}#humanReview .hrGrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
 #humanReview canvas{display:block;width:100%;height:390px;border-radius:10px;touch-action:none}#humanReview .hrPhoto{width:100%;height:390px;object-fit:contain;background:#303057;border-radius:10px;cursor:zoom-in}
 #humanReview .hrEvidence{line-height:1.65;padding:10px 0}#humanReview .hrLegend{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px}#humanReview .hrA{color:#ffae43}#humanReview .hrB{color:#30dce5}
 #humanReview textarea{display:block;width:100%;min-height:64px;box-sizing:border-box;margin:10px 0;background:#0a1524;color:#e7eff8;border:1px solid #57748d;border-radius:6px;padding:10px;font:inherit}
 #humanReview .hrStatus{min-height:24px;color:#a8d9f0}#humanReview small{color:#bccbda}#humanReview summary{cursor:pointer}#humanReview details pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto}
 #humanReview .hrVerdict{display:flex;gap:10px;align-items:center;flex-wrap:wrap}#humanReview .hrVerdict button{min-width:95px;padding:10px 14px}#humanReview .hrFacts{display:flex;gap:24px;flex-wrap:wrap;padding:12px;background:#172a3f;border-radius:8px}
 @media(max-width:900px){#humanReview .hrGrid{grid-template-columns:1fr}#humanReview canvas,#humanReview .hrPhoto{height:340px}}
 `;document.head.append(style);
 const panel=txt('section','','card');panel.id='humanReview';panel.setAttribute('aria-label','人工判定学习');
 const head=txt('div');head.append(txt('h2','你来判断 · 第 1 轮'),txt('small','从之前的干涉结果中选出的 3 对。橙色为对象 A，青色为对象 B；先看几何，再给判断。'));
 const tabs=txt('nav','','hrTabs');tabs.setAttribute('aria-label','案例切换');
 const title=txt('h3'),legend=txt('div','','hrLegend'),grid=txt('div','','hrGrid'),left=txt('div'),right=txt('div');
 const canvas=document.createElement('canvas');canvas.setAttribute('aria-label','当前对象对三维预览');
 const tools=txt('div','','hrTools'),photoTools=txt('div','','hrTools'),photo=document.createElement('img');photo.className='hrPhoto';
 const meshNote=txt('small','正在加载三维几何…'),photoNote=txt('small','CATIA 原生着色检查副本；图片仅用于定位，不能单独证明穿透。');
 left.append(txt('strong','导出层 · 可旋转三维'),tools,canvas,meshNote);right.append(txt('strong','CATIA 导入层 · 原生定位图'),photoTools,photo,photoNote);grid.append(left,right);
 const facts=txt('div','','hrFacts'),evidence=txt('div','','hrEvidence'),detail=document.createElement('details');detail.append(txt('summary','完整对象路径与证据记录'));const detailText=txt('pre');detail.append(detailText);
 const input=document.createElement('textarea');input.placeholder='可选：你为什么这样判断？例如正常贴合、需要复算、来源对应不足…';input.setAttribute('aria-label','判断理由');
 const verdict=txt('div','','hrVerdict'),status=txt('div','','hrStatus'),footer=txt('small','通过＝本轮无需处理；不通过＝需要处理；待确认＝证据不足。人工标注单独保存，不自动改正式结论。');
 const fullButton=txt('button','查看全量工作台');head.append(fullButton);panel.append(head,tabs,title,legend,grid,facts,evidence,detail,input,verdict,status,footer);document.querySelector('main').prepend(panel);
 const oldPanels=[...panel.parentElement.children,...document.querySelectorAll('body>header,body>.stats,body>.moduleControls')].filter(x=>x!==panel).map(x=>[x,x.hidden]);let labelMode=false;
 const setMode=()=>{for(const [node,wasHidden] of oldPanels)node.hidden=labelMode?true:wasHidden;fullButton.textContent=labelMode?'查看全量工作台':'只看人工判定';};fullButton.onclick=()=>{labelMode=!labelMode;setMode();};setMode();
 const view=new View(canvas);let index=0,current=null,pendingLabel=null,busy=false,lastMesh=null,shown='both';
 // Keep object colors stable when only one side is displayed.
 const buttons=[];for(const [label,text] of [['PASS','通过'],['FAIL','不通过'],['REVIEW','待确认']]){const b=txt('button',text);b.onclick=()=>{pendingLabel=label;paintVerdict();};buttons.push([label,b]);verdict.append(b);}
 const save=txt('button','保存判断'),clear=txt('button','撤回标注'),next=txt('button','下一个 →');verdict.append(save,clear,next);
 function paintVerdict(){for(const [label,b] of buttons){b.setAttribute('aria-pressed',String(label===pendingLabel));b.disabled=busy;}save.disabled=busy||!pendingLabel;clear.disabled=busy||!current?.human_label;next.disabled=busy||index===round.cases.length-1;input.disabled=busy;}
 function paintTabs(){tabs.replaceChildren();round.cases.forEach((c,i)=>{const b=txt('button',`${i+1}. ${c.ui.title}${c.human_label?' · 已标注':''}`);b.setAttribute('aria-pressed',String(i===index));b.disabled=busy;b.onclick=()=>showCase(i);tabs.append(b);});}
 async function commit(label){if(busy)return;busy=true;paintVerdict();paintTabs();status.textContent='正在保存…';try{const response=await fetch(base+'/human-review/label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:current.case_id,evidence_fingerprint:current.evidence_fingerprint,revision:current.label_revision||0,label,reason:input.value})});const result=await response.json();if(!response.ok)throw Error(result.error||'保存失败');round.cases[index]=result.case;current=result.case;pendingLabel=current.human_label;status.textContent=label?'已保存你的判断和理由，可随时修改。':'已撤回标注，历史记录保留。';}catch(error){status.textContent='未保存：'+error.message;}finally{busy=false;paintVerdict();paintTabs();}}
 save.onclick=()=>commit(pendingLabel);clear.onclick=()=>commit(null);next.onclick=()=>showCase(index+1);
 function orientation(yaw,pitch){view.yaw=yaw;view.pitch=pitch;view.dirty=true;}
 function fitLocal(){if(!current||!mesh)return;view.fit(current.pair,false);const b=current.ui.local_bounds_mm; if(b){view.center=b.min.map((v,i)=>(v+b.max[i])/2);view.span=Math.max(5,Math.hypot(...b.max.map((v,i)=>v-b.min[i]))*1.8);view.zoom=1;view.pan=[0,0];}view.dirty=true;}
 for(const [name,action] of [['局部',fitLocal],['对象对整体',()=>view.fit(current.pair,false)],['正面',()=>orientation(0,0)],['斜视',()=>orientation(.65,.3)],['俯视',()=>orientation(0,Math.PI/2)],['两件',()=>setShown('both')],['仅 A',()=>setShown('A')],['仅 B',()=>setShown('B')]]){const b=txt('button',name);b.onclick=action;tools.append(b);}
 const opacityLabel=txt('label','B 透明度 '),opacity=document.createElement('input');opacity.type='range';opacity.min='0.15';opacity.max='1';opacity.step='0.05';opacity.value='1';opacity.setAttribute('aria-label','对象 B 不透明度');opacity.oninput=()=>{view.opacityById={[current.pair[1]]:Number(opacity.value)};view.dirty=true;};opacityLabel.append(opacity);tools.append(opacityLabel);
 function setShown(mode){shown=mode;view.ids=mode==='both'?[...current.pair]:[current.pair[mode==='A'?0:1]];view.dirty=true;}
 // Left-drag rotation is available here in addition to the existing middle-button navigation.
 let pointer=null;canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;pointer=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});canvas.addEventListener('pointermove',e=>{if(!pointer)return;view.yaw+=(e.clientX-pointer[0])*.007;view.pitch+=(e.clientY-pointer[1])*.007;pointer=[e.clientX,e.clientY];view.dirty=true;});canvas.addEventListener('pointerup',()=>pointer=null);canvas.addEventListener('pointercancel',()=>pointer=null);
 function showPhoto(entry){photo.src=base+'/human-review/image?case='+encodeURIComponent(current.case_id)+'&image='+encodeURIComponent(entry.id);photo.alt=current.ui.title+' · '+entry.caption;photoNote.textContent=entry.caption+'。CATIA 原生检查副本；图像用于定位，不代替测量。';}
 photo.onclick=()=>{const dialog=document.createElement('dialog');dialog.style.cssText='max-width:94vw;width:1500px;background:#111d2d;color:white;border:1px solid #789;padding:12px';const close=txt('button','关闭大图'),large=document.createElement('img');large.src=photo.src;large.alt=photo.alt;large.style.cssText='display:block;max-width:100%;max-height:85vh;margin-top:10px';close.onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());dialog.append(close,large);document.body.append(dialog);dialog.showModal();};
 function showCase(i){if(busy)return;index=i;current=round.cases[i];pendingLabel=current.human_label;input.value=current.human_reason||'';title.textContent=current.case_id+' · '+current.ui.title;legend.replaceChildren(txt('strong','A：'+current.ui.objects[0].name,'hrA'),txt('strong','B：'+current.ui.objects[1].name,'hrB'));facts.replaceChildren(...current.ui.facts.map(x=>txt('span',x)));evidence.replaceChildren(...current.ui.evidence.map(x=>txt('div','• '+x)));detailText.textContent=JSON.stringify({objects:current.ui.objects,pair:current.pair,evidence_snapshot:current.evidence_snapshot},null,2);photoTools.replaceChildren();for(const entry of current.ui.images){const b=txt('button',entry.caption);b.onclick=()=>showPhoto(entry);photoTools.append(b);}showPhoto(current.ui.images.find(x=>x.id==='isometric-local')||current.ui.images[0]);view.paletteById={[current.pair[0]]:[1,.63,.22],[current.pair[1]]:[.12,.84,.88]};view.opacityById={};opacity.value='1';setShown('both');orientation(.65,.3);fitLocal();status.textContent=current.human_label?'已标注，可修改。':'尚未标注；请选择结论，再点“保存判断”。';paintTabs();paintVerdict();}
 showCase(0);
 function draw(){if(mesh&&lastMesh!==mesh){lastMesh=mesh;view.reset();fitLocal();}if(mesh){const missing=current.pair.filter(id=>!byId.has(id));meshNote.textContent=missing.length?'此案例缺少三维对象：'+missing.join('、'):'左键拖动旋转 · 滚轮放大 · 双击适配。网格用于观察，微小交集以精确测量为准。';if(!missing.length)view.draw(true,false);}requestAnimationFrame(draw);}draw();
})().catch(error=>console.error('人工判定页面加载失败',error));
