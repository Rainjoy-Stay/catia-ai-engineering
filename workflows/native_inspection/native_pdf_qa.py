import json,re
from pathlib import Path
from PIL import Image,ImageDraw
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'output/全量原生DMU检查_20261012';Q=ROOT/'output/pdf/qa_20261013'
meta=json.loads((F/'resume-report-generation.json').read_text(encoding='utf8'));reader=PdfReader(meta['pdf'])
assert len(reader.pages)==95
images=sorted(Q.glob('page-*.png'));assert len(images)==95
for off in range(0,95,18):
 sheet=Image.new('RGB',(1500,650),'#ddd');draw=ImageDraw.Draw(sheet)
 for k,p in enumerate(images[off:off+18]):
  im=Image.open(p).convert('RGB');im.thumbnail((245,210));x=(k%6)*250;y=(k//6)*216
  sheet.paste(im,(x,y+15));draw.text((x+5,y+1),p.stem,fill='black')
 sheet.save(Q/f'qa-sheet-{off//18+1}.jpg',quality=94)
source=json.loads((F/'resume-image-index.json').read_text(encoding='utf8'))
checks=[]
for i,r in enumerate(source['rows'],8):
 page=reader.pages[i];txt=page.extract_text()
 assert r['issue_id'] in txt
 assert '整体定位图' in txt and '局部细节图' in txt
 assert len(page.images)==2
 checks.append({'page':i+1,'issue_id':r['issue_id'],'embedded_images':len(page.images)})
(F/'resume-pdf-qa.json').write_text(json.dumps({'pages':95,'issue_pages':checks,'rendered_pages':95,'visual_review':'PENDING'},ensure_ascii=False,indent=2),encoding='utf8')
print({'pages':len(reader.pages),'issue_pages':len(checks),'all_rendered':len(images)})
