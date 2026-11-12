"""Create a disposable STEP sample from a few Bodies of the active CATPart."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]; ROOT=PROJECT.parent
for value in (str(PROJECT),str(ROOT/"scripts")):
    if value not in sys.path: sys.path.insert(0,value)
from r18_connection import R18Connection

def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--output",type=Path,required=True); p.add_argument("--count",type=int,default=6); p.add_argument("--scan",type=int,default=120); p.add_argument("--duplicate-smallest",action="store_true"); a=p.parse_args()
    c=R18Connection(); c.connect(); app=c.app; source=app.ActiveDocument
    if not str(source.Name).lower().endswith(".catpart"): raise RuntimeError("Active document must be a CATPart")
    part=source.Part; saved_before=bool(source.Saved); bodies_before=int(part.Bodies.Count); spa=c.spa_workbench
    records=[]
    for index in range(1,min(bodies_before,a.scan)+1):
        body=part.Bodies.Item(index)
        try:
            m=spa.GetMeasurable(part.CreateReferenceFromObject(body)); cog=[0.0,0.0,0.0]; m.GetCOG(cog)
            volume=float(m.Volume)*1e9
            if volume>0: records.append({"index":index,"name":str(body.Name),"cog_mm":[v*1000 for v in cog],"volume_mm3":volume})
        except Exception: pass
    if len(records)<a.count: raise RuntimeError(f"Only {len(records)} measurable solid Bodies found")
    # Prefer the smallest real solids so the smoke test remains fast and inexpensive.
    chosen=sorted(records,key=lambda item:item["volume_mm3"])[:a.count]
    if a.duplicate_smallest: chosen=[dict(chosen[0]) for _ in range(a.count)]
    target=app.Documents.Add("Part")
    try:
        target.Product.PartNumber="CATIA_AI_SMALL_VALIDATION"; target_part=target.Part
        for position,item in enumerate(chosen):
            source.Activate(); ss=source.Selection; ss.Clear(); ss.Add(part.Bodies.Item(item["index"])); ss.Copy(); ss.Clear()
            target.Activate(); dest=target_part.MainBody if position==0 else target_part.Bodies.Add(); dest.Name=f"SAMPLE_{position+1:02d}_{item['name']}"
            ts=target.Selection; ts.Clear(); ts.Add(dest)
            try: ts.PasteSpecial("CATPrtResultWithOutLink")
            except Exception: ts.PasteSpecial("CATPrtResult")
            ts.Clear()
        target_part.Update(); a.output.parent.mkdir(parents=True,exist_ok=True); target.ExportData(str(a.output.resolve()),"stp")
    finally:
        try: target.Close()
        finally: source.Activate()
    audit={"source_document":str(source.Name),"source_saved_before":saved_before,"source_saved_after":bool(source.Saved),"source_body_count_before":bodies_before,"source_body_count_after":int(part.Bodies.Count),"selected_bodies":chosen,"sample_step":str(a.output.resolve()),"sample_size_bytes":a.output.stat().st_size if a.output.exists() else 0,"source_modified":saved_before!=bool(source.Saved) or bodies_before!=int(part.Bodies.Count)}
    print(json.dumps(audit,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
