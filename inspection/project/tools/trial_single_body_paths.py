"""Structured MCP singleton exports for selected diagnostic pilot Bodies."""
import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'project/output/path-comparison-20261001'

async def run():
    env=dict(os.environ,PYTHONPATH=str(ROOT/'vendor/catia-v5-mcp-server'),PYTHONIOENCODING='utf-8')
    params=StdioServerParameters(command=sys.executable,args=['-m','catia_mcp.server'],env=env,cwd=str(ROOT))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer,read_timeout_seconds=timedelta(minutes=20)) as session:
            await session.initialize()
            for name,args in [('catia_connect',{}),('catia_activate_document',{'name':'full_all_features.CATPart'})]:
                result=await session.call_tool(name,args)
                if result.isError: raise RuntimeError(str(result.content))
            for index in (1,2,3,5,9,31,38):
                directory=OUT/('body-'+str(index))
                if (directory/'benchmark.json').exists():
                    audit=json.loads((directory/'benchmark.json').read_text(encoding='utf-8'))
                    if audit['status']=='COMPLETE': continue
                    raise RuntimeError('Incomplete existing audit; not overwritten')
                print('EXPORT_BODY '+str(index),flush=True)
                result=await session.call_tool('catia_benchmark_batch_copy',{
                    'source_name':'full_all_features.CATPart','body_indices':[index],
                    'output_directory':str(directory)})
                if result.isError: raise RuntimeError(str(result.content))
                audit=json.loads((directory/'benchmark.json').read_text(encoding='utf-8'))
                print('BODY '+str(index)+' AUDIT_STATUS '+audit['status'],flush=True)
            result=await session.call_tool('catia_get_model_manifest',{
                'include_parameters':False,'output_path':str(OUT/'source-after.json')})
            if result.isError: raise RuntimeError(str(result.content))
            print('COMPLETE',flush=True)

if __name__=='__main__': asyncio.run(run())
