"""Annotate only real CATIA object projections; preserve all native originals."""
import json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
F=Path(__file__).resolve().parents[1]/'output/全量原生DMU检查_20261012'
audit=json.loads((F/'resume-capture-audit.json').read_text(encoding='utf8'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mask(path,crop):
 a=np.asarray(Image.open(path).convert('RGB')).astype(int)
 m=(a[:,:,0]-a[:,:,2]>35)&(a[:,:,0]>75)&(a[:,:,1]>30)&(a[:,:,1]<230)
 keep=np.zeros(m.shape,bool);l,t,r,b=crop;keep[t:b,l:r]=True
 return m&keep
rows=[]
for j in audit['jobs']:
 folder=Path(j['folder']);im=Image.open(folder/'context-raw.jpg');w,h=im.size
 crop=[round(w*.2),round(h*.15),round(w*.86),round(h*.92)]
 row={**j,'crop':crop,'raw_size':[w,h],'images':{},'qa_status':'PENDING_VISUAL_REVIEW'}
 for role in ('context','detail'):
  raw=folder/(role+'-raw.jpg');locator=folder/(role+'-locator.jpg')
  assert Image.open(raw).size==(w,h)
  m=mask(locator,crop);ys,xs=np.where(m)
  locator_id=j['object_ids'][1]
  if len(xs)<12 and role=='context':
   locator=folder/'context-locator-a.jpg';m=mask(locator,crop);ys,xs=np.where(m);locator_id=j['object_ids'][0]
  entry={'raw':str(raw),'locator':str(locator),'locator_id':locator_id,'raw_sha256':digest(raw),'locator_sha256':digest(locator),'roi_method':'ISOLATED_REAL_OBJECT_SAME_NATIVE_CAMERA','status':'NEEDS_REVIEW'}
  if len(xs)>=12:
   box=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
   if box[0]>crop[0]+5 and box[1]>crop[1]+5 and box[2]<crop[2]-5 and box[3]<crop[3]-5:
    pad=16;box=[max(crop[0]+2,box[0]-pad),max(crop[1]+2,box[1]-pad),min(crop[2]-2,box[2]+pad),min(crop[3]-2,box[3]+pad)]
    image=Image.open(raw).convert('RGB');ImageDraw.Draw(image).rectangle(box,outline=(255,35,35),width=4)
    out=folder/(role+'.jpg');image.crop(crop).save(out,quality=94)
    entry.update(status='PROJECTION_CHECK_PASSED',annotated=str(out),annotated_sha256=digest(out),box=box,image_size=Image.open(out).size)
   else:entry['reason']='Target projection touches viewport boundary'
  else:entry['reason']='Actual target projection too small'
  if 'annotated' not in entry:
   out=folder/(role+'-unmarked.jpg');Image.open(raw).convert('RGB').crop(crop).save(out,quality=94);entry['unmarked']=str(out)
  row['images'][role]=entry
 if any(v['status']=='NEEDS_REVIEW' for v in row['images'].values()):row['qa_status']='NEEDS_REVIEW'
 rows.append(row)
out={'rows':rows,'restoration':audit['restoration'],'viewport_measurement':'Verified native raw canvas; crop removes tree, upper-right compass and lower-right axes; inspect pilot before accepting batch'}
(F/'resume-image-index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
qa=F/'qa-resume';qa.mkdir(exist_ok=True)
for off in range(0,len(rows),12):
 sheet=Image.new('RGB',(1600,1800),'white');draw=ImageDraw.Draw(sheet)
 for k,row in enumerate(rows[off:off+12]):
  x=(k%2)*800;y=(k//2)*300
  draw.text((x+8,y+4),row['issue_id']+' '+row['geometry_fact']['status'],fill='black')
  for col,role in enumerate(('context','detail')):
   e=row['images'][role];p=e.get('annotated') or e.get('unmarked');image=Image.open(p).convert('RGB');image.thumbnail((395,265));sheet.paste(image,(x+col*400,y+24))
 sheet.save(qa/f'new-dual-sheet-{off//12+1}.jpg',quality=93)
print({'rows':len(rows),'needs_review':sum(r['qa_status']=='NEEDS_REVIEW' for r in rows)})
