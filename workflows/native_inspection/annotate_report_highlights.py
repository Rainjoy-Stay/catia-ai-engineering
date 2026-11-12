"""Annotate new UI-colored captures; require measured viewport/compass/target ROIs."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/project/tools'))
from report_highlight_bounds import highlight_bounds

def main():
 from PIL import Image,ImageDraw
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--jobs',type=Path,required=True,help='JSON list: source, label, viewport, compass, target_roi, excluded')
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True);records=[]
 for i,job in enumerate(json.loads(args.jobs.read_text(encoding='utf-8')),1):
  source=Path(job['source']);im=Image.open(source).convert('RGB')
  result=highlight_bounds(im,viewport=job['viewport'],compass=job['compass'],target_roi=job['target_roi'],excluded=job.get('excluded',[]))
  output=None
  if result['status']=='OK':
   x0,y0,x1,y1=result['box'];draw=ImageDraw.Draw(im);draw.rectangle((x0,y0,x1,y1),outline='red',width=10)
   # Use the existing red label treatment; fit it inside the recorded viewport.
   top=max(job['viewport'][1],y0-42);right=min(job['viewport'][2],x0+460)
   draw.rectangle((x0,top,right,top+38),fill='white',outline='red',width=3)
   draw.text((x0+8,top+10),job['label'],fill=(210,0,0))
   output=args.output/f'{i:03d}-{source.stem}.jpg';im.save(output,quality=95)
  records.append(dict(source=str(source),output=str(output) if output else None,**result))
 (args.output/'标注审核索引.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'{len(records)} images; {sum(r["status"]!="OK" for r in records)} need review')

if __name__=='__main__':main()
