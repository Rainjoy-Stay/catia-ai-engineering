import win32com.client,json,pathlib,time
root=pathlib.Path(r'release_build\CATIA_V5_AI_DROP_V4_5_DEV\project');P=root/'artifacts'/'spatial_box_complex';shots=json.loads((P/'catia_screenshot_index.json').read_text(encoding='utf-8'));idx=[1,738,739,740,741,817,819,821,823,825,827,828,830,833,834,835,836,837,838,839,840,841];out=P/'catia_context_raw';out.mkdir(exist_ok=True)
app=win32com.client.GetActiveObject('CATIA.Application');doc=next(app.Documents.Item(i) for i in range(1,app.Documents.Count+1) if app.Documents.Item(i).Name=='涡轮发动机.CATPart');doc.Activate();part=doc.Part;sel=doc.Selection;v=app.ActiveWindow.ActiveViewer
def add(i):
 b=part.Bodies.Item(i);sel.Add(b)
 for j in range(1,b.Shapes.Count+1):sel.Add(b.Shapes.Item(j))
for x in shots:
 sel.Clear()
 for i in idx:add(i)
 sel.VisProperties.SetShow(0);sel.VisProperties.SetRealColor(185,190,198,1);sel.VisProperties.SetRealOpacity(52,1);sel.Clear()
 for i,c in ((x['body_a'],(255,161,56)),(x['body_b'],(31,214,224))):
  add(i);sel.VisProperties.SetRealColor(*c,1);sel.VisProperties.SetRealOpacity(255,1);sel.Clear()
 sel.Add(part.Bodies.Item(x['body_a']));sel.Add(part.Bodies.Item(x['body_b']));v.Reframe();time.sleep(.12)
 target=out/f"{x['order']:02d}_BODY_{x['body_a']}_{x['body_b']}.jpg";v.CaptureToFile(5,str(target.resolve()))
sel.Clear()
for i in idx:add(i)
sel.VisProperties.SetShow(0);sel.VisProperties.SetRealOpacity(255,1);sel.VisProperties.SetRealColor(255,215,0,1);sel.Clear()
for i in idx:sel.Add(part.Bodies.Item(i))
v.Reframe();print(json.dumps({'captured':len(shots),'final_selection':sel.Count2,'saved':bool(doc.Saved)}))
