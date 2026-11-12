"""One bounded worker extracting local exact common and analytic face evidence."""
import argparse
import json
from pathlib import Path
from catia_checker.occt_brep import OCCTBRepModel


def main():
    p = argparse.ArgumentParser()
    p.add_argument('first', type=Path); p.add_argument('second', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    model = OCCTBRepModel(); model.load_brep('A', a.first); model.load_brep('B', a.second)
    result = model.local_overlap_evidence('A','B')
    for sid in ('A', 'B'):
        ledger = model.solid_face_provenance(sid)
        result[f'faces_{sid.lower()}'] = [model.describe(f) for f in ledger['face_ids']]
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
