"""Run the structured MCP batch-copy benchmark, then independently verify STEP mappings."""
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

async def run(args):
    env=dict(os.environ,PYTHONPATH=str(ROOT/'vendor/catia-v5-mcp-server'),PYTHONIOENCODING='utf-8')
    params=StdioServerParameters(command=sys.executable,args=['-m','catia_mcp.server'],env=env,cwd=str(ROOT))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer,read_timeout_seconds=timedelta(minutes=20)) as session:
            await session.initialize()
            await session.call_tool('catia_connect',{})
            await session.call_tool('catia_activate_document',{'name':args.source})
            if args.spatial_only:
                result=await session.call_tool('catia_capture_body_spatial_facts',{'source_name':args.source,
                    'body_indices':list(range(1,args.count+1)), 'output_path':str((args.directory/'spatial-probe.json').resolve())})
                for item in result.content:
                    if getattr(item,'text',None): print(item.text,flush=True)
                return
            result=await session.call_tool('catia_benchmark_batch_copy',{'source_name':args.source,
                'body_indices':list(range(1,args.count+1)), 'output_directory':str(args.directory.resolve())})
            for item in result.content:
                if getattr(item,'text',None): print(item.text,flush=True)
    path=args.directory/'benchmark.json'
    audit=json.loads(path.read_text(encoding='utf-8'))
    if audit['status']!='COMPLETE': raise RuntimeError('CATIA benchmark incomplete')
    sys.path.insert(0,str(ROOT/'project'))
    from catia_checker.occt_brep import OCCTBRepModel
    from catia_checker.geometry_fingerprint import match_geometry_records_with_labels
    verification=[]
    for case in audit['cases']:
        model=OCCTBRepModel(); manifest=model.load_step(case['step_path'],lightweight=True)
        objects=[s for s in manifest['shapes'] if s['shape_id']!=manifest['root_shape_id']]
        matched=match_geometry_records_with_labels(objects,case['mapping'],source_id='shape_id',
            target_id='source_body_index',source_label='source_name',target_label='batch_body_name',
            tolerances={'relative_volume':1e-4,'relative_area':1e-4,'centroid_mm':1e-3,'bounds_mm':1e-3})
        verification.append({'mode':case['mode'],'geometry_count':len(objects),
                             'matches':matched,'count_verified':len(objects)==len(case['mapping'])})
    result={'cases':verification,'is_complete':all(c['count_verified'] and c['matches']['is_complete'] for c in verification),
            'full_model_coverage':False,'formal_check_executed':False}
    (args.directory/'occt-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'step_mapping_verified':result['is_complete'],'counts':[c['geometry_count'] for c in verification]}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default='full_all_features.CATPart')
    parser.add_argument('--count',type=int,default=40)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--spatial-only',action='store_true')
    asyncio.run(run(parser.parse_args()))
