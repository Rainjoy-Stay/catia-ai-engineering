import win32com.client,json,pathlib,time
root=pathlib.Path(r'release_build\CATIA_V5_AI_DROP_V4_5_DEV\project');P=root/'artifacts'/'spatial_box_complex';analysis=json.loads((P/'spatial_box_analysis.json').read_text(encoding='utf-8'));idx=[x['index'] for x in analysis['body_records']]
issues=[r for r in analysis['records'] if r.get('fact',{}).get('intersection_volume_mm3',0)>0 or r['decision']['category']=='CONTACT_OR_COPLANAR']
outdir=P/'catia_native_screenshots';outdir.mkdir(exist_ok=True)
app=win32com.client.GetActiveObject('CATIA.Application');app.Visible=True;doc=next(app.Documents.Item(i) for i in range(1,app.Documents.Count+1) if app.Documents.Item(i).Name=='涡轮发动机.CATPart');doc.Activate();part=doc.Part;sel=doc.Selection;v=app.ActiveWindow.ActiveViewer;shots=[]
def add_body(i):
 b=part.Bodies.Item(i);sel.Add(b)
 try:
  for j in range(1,b.Shapes.Count+1):sel.Add(b.Shapes.Item(j))
 except:pass
for n,r in enumerate(issues,1):
 sel.Clear()
 for i in idx:add_body(i)
 sel.VisProperties.SetShow(1);sel.Clear()
 for i,color in ((r['body_a'],(255,210,0)),(r['body_b'],(230,35,35))):
  add_body(i);sel.VisProperties.SetShow(0);sel.VisProperties.SetRealColor(*color,1);sel.VisProperties.SetRealOpacity(96 if i==1 else 255,1);sel.Clear()
 sel.Add(part.Bodies.Item(r['body_a']));sel.Add(part.Bodies.Item(r['body_b']));v.Reframe();time.sleep(.2)
 target=outdir/f"{n:02d}_BODY_{r['body_a']}_{r['body_b']}.jpg";v.CaptureToFile(5,str(target.resolve()))
 shots.append({'order':n,'body_a':r['body_a'],'name_a':r['name_a'],'body_b':r['body_b'],'name_b':r['name_b'],'category':r['decision']['category'],'volume_mm3':r.get('fact',{}).get('intersection_volume_mm3',0),'image':str(target.resolve())})
# restore complex region as one selected yellow set
sel.Clear()
for i in idx:add_body(i)
sel.VisProperties.SetShow(0);sel.VisProperties.SetRealOpacity(255,1);sel.VisProperties.SetRealColor(255,215,0,1);sel.Clear()
for i in idx:sel.Add(part.Bodies.Item(i))
v.Reframe();(P/'catia_screenshot_index.json').write_text(json.dumps(shots,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'screenshot_count':len(shots),'final_selection_count':sel.Count2,'saved':bool(doc.Saved)},ensure_ascii=False))
