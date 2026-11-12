from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import json
P=Path('artifacts/spatial_box_complex');shots=json.loads((P/'catia_screenshot_index.json').read_text(encoding='utf-8'));ctx=P/'catia_context_boxed';det=P/'catia_detail_boxed';ctx.mkdir(exist_ok=True);det.mkdir(exist_ok=True)
def annotate(src,dst,label):
 im=Image.open(src).convert('RGB');pix=im.load();xs=[];ys=[];x0=300;x1=min(1780,im.width)
 for y in range(25,im.height-25):
  for x in range(x0,x1):
   r,g,b=pix[x,y]
   if (r>170 and g<115 and b<115) or (r>185 and g>125 and b<105):xs.append(x);ys.append(y)
 if xs:
  pad=28;bx=[max(x0,min(xs)-pad),max(20,min(ys)-pad),min(x1,max(xs)+pad),min(im.height-20,max(ys)+pad)]
  if bx[2]-bx[0]<90:
   mid=(bx[0]+bx[2])//2;bx[0]=max(x0,mid-45);bx[2]=min(x1,mid+45)
  if bx[3]-bx[1]<90:
   mid=(bx[1]+bx[3])//2;bx[1]=max(20,mid-45);bx[3]=min(im.height-20,mid+45)
 else:bx=[750,350,1050,650]
 dr=ImageDraw.Draw(im);dr.rectangle(tuple(bx),outline=(255,0,0),width=10);tw=460;ty=max(2,bx[1]-42);dr.rectangle((bx[0],ty,min(im.width-10,bx[0]+tw),ty+38),fill='white',outline='red',width=3);dr.text((bx[0]+8,ty+10),label,fill=(210,0,0));im.save(dst,quality=95);return bx
rows=[]
for x in shots:
 name=f"{x['order']:02d}_BODY_{x['body_a']}_{x['body_b']}.jpg";label=f"INTERFERENCE  Body {x['body_a']} / {x['body_b']}";cb=annotate(P/'catia_context_raw'/name,ctx/name,label);db=annotate(Path(x['image']),det/name,label);rows.append({**x,'context_image':str((ctx/name).resolve()),'detail_image':str((det/name).resolve()),'context_box_px':cb,'detail_box_px':db})
(P/'catia_dual_view_index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print(len(rows))
