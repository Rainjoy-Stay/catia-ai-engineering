"""Capture read-only spatial source evidence and reverify the completed copy trial."""
import argparse
import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[2]

async def run(directory):
    audit=json.loads((directory/'benchmark.json').read_text(encoding='utf-8'))
    if audit['status']!='COMPLETE': raise RuntimeError('Benchmark not complete')
    spatial_path=directory/'spatial-source-facts.json'
    env=dict(os.environ,PYTHONPATH=str(ROOT/'vendor/catia-v5-mcp-server'),PYTHONIOENCODING='utf-8')
    params=StdioServerParameters(command=sys.executable,args=['-m','catia_mcp.server'],env=env,cwd=str(ROOT))
    if not spatial_path.exists():
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=timedelta(minutes=10)) as session:
                await session.initialize(); await session.call_tool('catia_connect',{})
                await session.call_tool('catia_activate_document',{'name':audit['source_document']})
                result=await session.call_tool('catia_capture_body_spatial_facts',{
                    'source_name':audit['source_document'],'body_indices':audit['body_indices'],'output_path':str(spatial_path.resolve())})
                for item in result.content:
                    if getattr(item,'text',None):print(item.text,flush=True)
    spatial=json.loads(spatial_path.read_text(encoding='utf-8'))
    source_facts={r['source_body_index']:r for r in spatial['records']}
    sys.path.insert(0,str(ROOT/'project'))
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.geometry_fingerprint import match_geometry_records_with_labels
    verification=[]
    for case in audit['cases']:
        model=OCCTBRepModel(); manifest=model.load_step(case['step_path'],lightweight=True)
        objects=[s for s in manifest['shapes'] if s['shape_id']!=manifest['root_shape_id']]
        records=[{**r,**source_facts[r['source_body_index']]} for r in case['mapping']]
        matched=match_geometry_records_with_labels(objects,records,source_id='shape_id',
            target_id='source_body_index',source_label='source_name',target_label='batch_body_name',
            tolerances={'relative_volume':1e-4,'relative_area':1e-4,'centroid_mm':1e-3,'bounds_mm':1e-3})
        verification.append({'mode':case['mode'],'geometry_count':len(objects),'matches':matched,
                             'count_verified':len(objects)==len(records)})
    result={'cases':verification,'is_complete':all(c['count_verified'] and c['matches']['is_complete'] for c in verification),
            'spatial_source_evidence_verified':spatial['all_centroids_verified'],
            'full_model_coverage':False,'formal_check_executed':False}
    (directory/'occt-spatial-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'step_mapping_verified':result['is_complete'],
                      'matched_counts':[c['matches']['matched_count'] for c in verification]}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    asyncio.run(run(parser.parse_args().directory))
