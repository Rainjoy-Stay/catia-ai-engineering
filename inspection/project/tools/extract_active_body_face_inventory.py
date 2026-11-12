"""Export active CATPart one Body at a time and build exact traceable face inventory."""
from __future__ import annotations
import argparse,json,shutil,sys,tempfile
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]; ROOT=PROJECT.parent
for value in (str(PROJECT),str(ROOT/"scripts"),str(PROJECT/"tools")):
    if value not in sys.path: sys.path.insert(0,value)
from catia_checker.catia_body_batches import export_body_batches
from catia_checker.face_traceability import bind_single_body_faces
from inspect_active_large_single_part import run_child_command
from r18_connection import R18Connection

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--output",type=Path,required=True); parser.add_argument("--body-indices",type=int,nargs="+"); parser.add_argument("--timeout-per-body",type=float,default=120); args=parser.parse_args()
    connection=R18Connection(); connection.connect(); doc=connection.active_document
    if not str(doc.Name).lower().endswith(".catpart"): raise RuntimeError("Active document must be a CATPart")
    before=(bool(doc.Saved),int(doc.Part.Bodies.Count)); temp=Path(tempfile.mkdtemp(prefix="catia-face-inventory-")); faces=[]; errors=[]; audit=None
    try:
        audit=export_body_batches(connection.app,doc,temp,batch_size=1,body_indices=args.body_indices)
        for step,body in zip(audit["batch_files"],audit["body_mapping"]):
            result=temp/f"{step.stem}-faces.json"; command=[sys.executable,str(PROJECT/"tools"/"inspect_step_face_inventory.py"),str(step),"--output",str(result)]
            try:
                run_child_command(command,result,args.timeout_per_body); bound=bind_single_body_faces(json.loads(result.read_text(encoding="utf-8")),body); faces.extend(bound["faces"])
                if bound["error"]: errors.append(bound["error"])
            except Exception as exc:
                errors.append({"code":"FACE_INVENTORY_BODY_FAILED","source_body_index":body["source_body_index"],"message":str(exc)})
    finally:
        after=(bool(doc.Saved),int(doc.Part.Bodies.Count)); shutil.rmtree(temp,ignore_errors=True)
    if after!=before: raise RuntimeError("Source CATPart state changed during face inventory")
    payload={"schema_version":"catia-active-body-faces.v1.0","document":str(doc.Name),"faces":faces,"face_count":len(faces),"body_count":len(audit["body_mapping"]) if audit else 0,"coverage_complete":not errors and bool(audit and audit["full_source_coverage"]),"mapping_errors":errors,"source_document_saved_before":before[0],"source_document_saved_after":after[0],"source_modified":False,"cleanup_verified":not temp.exists(),"geometry_authority":"OCCT_EXACT_BREP_FROM_SINGLE_CATIA_BODY_EXPORT","mesh_used":False}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(args.output); return 1 if errors else 0
if __name__=="__main__": raise SystemExit(main())
