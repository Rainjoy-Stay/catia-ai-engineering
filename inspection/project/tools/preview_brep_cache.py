"""Create a bounded display preview from an existing inspection BREP cache."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_brep import OCCTBRepModel,_bounds
from catia_checker.monitor_preview import export_preview

def main():
    p=argparse.ArgumentParser();p.add_argument('cache',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    files=sorted(a.cache.glob('*.brep'));selected=files
    m=OCCTBRepModel();shapes=[];mapping={}
    for f in selected:
        sid=f.stem.replace('_STEP_SOLID','::STEP_SOLID');m.load_brep(sid,f)
        shapes.append({'shape_id':sid,'bounds_mm':_bounds(m._shape(sid))})
        mapping[sid]={'batch_id':'B','local_shape_id':sid}
    a.output.mkdir(parents=True,exist_ok=True)
    export_preview({'B':m},{'shapes':shapes,'mapping':mapping},a.output)
    preview=a.output/'preview.json';v=json.loads(preview.read_text());v.update(truncated=False,sampled=False,source_object_count=len(files));preview.write_text(json.dumps(v),encoding='utf-8')
    print('LIVE_PREVIEW_READY',len(v['objects']),'display objects from',len(files),'cached solids')
if __name__=='__main__':main()
