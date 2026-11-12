import argparse
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.shared_topology import verify_seed_topology


def main():
    p=argparse.ArgumentParser(); p.add_argument('detail',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); detail=json.loads(a.detail.read_text(encoding='utf-8'))
    sid=detail['solid']['shape_id']; model=OCCTBRepModel(); model.load_brep(sid,a.detail.with_suffix('.brep'))
    model.solid_face_provenance(sid)
    result=verify_seed_topology(model,detail['support_tangency_seeds'],detail['faces'])
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
