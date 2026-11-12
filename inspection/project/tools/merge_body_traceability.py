from __future__ import annotations
import argparse,json,sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(PROJECT))
from catia_checker.body_traceability import merge_verified_body_mapping

def main():
    p=argparse.ArgumentParser(); p.add_argument("result",type=Path); p.add_argument("replay",type=Path); p.add_argument("rescue",type=Path); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    payload=json.loads(a.result.read_text(encoding="utf-8")); replay=json.loads(a.replay.read_text(encoding="utf-8")); rescue=json.loads(a.rescue.read_text(encoding="utf-8"))
    audit=merge_verified_body_mapping(payload,replay,rescue); a.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(audit,ensure_ascii=False)); return 0 if audit["is_complete"] else 2
if __name__=="__main__": raise SystemExit(main())
