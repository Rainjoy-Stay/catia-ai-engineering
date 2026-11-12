import json
from pathlib import Path
from PIL import Image,ImageDraw
F=Path(__file__).resolve().parents[1]/'output/全量原生DMU检查_20261012'
a=json.loads((F/'capture-audit.json').read_text(encoding='utf8'))
rows=[j for j in a['jobs'] if all(o['kind']=='SOLID' for o in j['objects'])]
out=F/'qa-resume';out.mkdir(exist_ok=True)
for off in range(0,len(rows),20):
 im=Image.new('RGB',(1600,1300),'white');draw=ImageDraw.Draw(im)
 for k,j in enumerate(rows[off:off+20]):
  s=Image.open(j['detail']['raw']).convert('RGB');w,h=s.size
  s=s.crop((int(w*.2),int(h*.12),w-30,h-90));s.thumbnail((395,230))
  x=(k%4)*400;y=(k//4)*260;im.paste(s,(x,y+25))
  draw.text((x+5,y+5),j['issue_id']+'  '+str(round(j['native']['interference_depth_mm'],2))+' mm',fill='black')
 im.save(out/f'solid-sheet-{off//20+1}.jpg')
print({'rows':len(rows),'sheets':(len(rows)+19)//20})
