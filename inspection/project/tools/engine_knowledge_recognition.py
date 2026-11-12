from __future__ import annotations
import argparse, json
from pathlib import Path
from catia_checker.model_understanding.knowledge_inference import compile_knowledge_base, infer_object, load_knowledge_base, save_knowledge_base
from catia_checker.model_understanding.semantic_learning import load_jsonl

def main():
    p=argparse.ArgumentParser(description="发动机少样本知识识别"); s=p.add_subparsers(dest="command",required=True)
    b=s.add_parser("build-kb"); b.add_argument("--config",required=True); b.add_argument("--cases"); b.add_argument("--output",required=True)
    r=s.add_parser("recognize"); r.add_argument("--kb",required=True); r.add_argument("--input",required=True); r.add_argument("--output",required=True)
    a=p.parse_args()
    if a.command=="build-kb":
        kb=compile_knowledge_base(json.loads(Path(a.config).read_text(encoding="utf-8-sig")),load_jsonl(a.cases) if a.cases else [])
        save_knowledge_base(kb,a.output); print(json.dumps({"status":"OK","systems":len(kb["systems"]),"cases":len(kb["case_library"])},ensure_ascii=False)); return 0
    rows=load_jsonl(a.input,labelled=False); results=[infer_object(load_knowledge_base(a.kb),v) for v in rows]
    Path(a.output).write_text("\n".join(json.dumps(v,ensure_ascii=False) for v in results)+"\n",encoding="utf-8")
    print(json.dumps({"status":"OK","objects":len(results),"review":sum(v["requires_human_review"] for v in results)},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
