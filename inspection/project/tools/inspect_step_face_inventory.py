"""Extract exact OCCT face inventory from one STEP in an isolated process."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path: sys.path.insert(0,str(PROJECT))
from catia_checker.occt_brep import OCCTBRepModel

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("step",type=Path); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    payload=OCCTBRepModel().load_step_faces(args.step)
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(args.output); return 0
if __name__=="__main__": raise SystemExit(main())
