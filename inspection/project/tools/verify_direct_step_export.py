"""Verify topology in a completed direct STEP export; never operates CATIA."""
import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from catia_checker.occt_brep import independent_geometry, _bounds

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--check-bounds',action='store_true')
    args=parser.parse_args()
    started=time.perf_counter()
    with args.source.open('rb') as stream:
        stream.seek(max(0,args.source.stat().st_size-4096))
        if b'END-ISO-10303-21;' not in stream.read():
            raise RuntimeError('STEP is not complete; do not inspect a partial export')
    reader=STEPControl_Reader()
    if reader.ReadFile(str(args.source))!=IFSelect_RetDone:
        raise RuntimeError('OCCT cannot read STEP')
    reader.TransferRoots()
    root=reader.OneShape()
    if root.IsNull():raise RuntimeError('No transferred geometry')
    geometry=independent_geometry(root)
    counts=dict(Counter(kind for kind,_ in geometry))
    result={'file':str(args.source),'size_bytes':args.source.stat().st_size,
            'occt_import_seconds':time.perf_counter()-started,'independent_geometry':counts,
            'source_name_mapping_verified':False,'coverage_verified':False,
            'note':'Topology counts are not proof of full CATIA coverage or name mapping'}
    if args.check_bounds:
        abnormal=[]
        for index,(kind,shape) in enumerate(geometry,1):
            try:
                bounds=_bounds(shape)
                if not bounds or any(not math.isfinite(v) or abs(v)>=1e90 for v in bounds['min']+bounds['max']):
                    abnormal.append({'index':index,'kind':kind,'bounds':bounds})
            except Exception as exc:
                abnormal.append({'index':index,'kind':kind,'error':str(exc)})
        result['abnormal_bounds']=abnormal
        result['abnormal_bounds_count']=len(abnormal)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
