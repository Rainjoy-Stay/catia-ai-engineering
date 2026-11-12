"""Measure candidate identities without promoting them to verified mappings."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'project'))
from catia_checker.occt_session_cache import atomic_json
from catia_checker.geometry_fingerprint import compare_geometry_features

async def main():
    run=ROOT/'project/output/monitor/full-bulk-20261001-01'
    audit=json.loads((run/'shape-review/ten-pair-mapping-audit.json').read_text(encoding='utf-8'))
    objects=json.loads((run/'registry.json').read_text(encoding='utf-8'))['objects'];rows=[]
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/start_mcp.py')],cwd=str(ROOT),env=dict(os.environ,PYTHONIOENCODING='utf-8',CATIA_AGENT_MODE='full'))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize();await session.call_tool('catia_connect',{})
            for target in audit['rows']:
                if target['status']!='REJECTED_MAPPING_AUDITED':continue
                candidate=target['candidates'][0];output=run/f"shape-review/live-candidate-body-{candidate['source_body_index']:04d}.json"
                row={'shape_id':target['shape_id'],'candidate':candidate,'mapping_verified':False}
                if not output.exists():
                    result=await session.call_tool('catia_dev_dispatch',{'operation':'read_body_spa_identity','arguments':{
                        'document_name':'full_all_features.CATPart','document_path':str(ROOT.parent/'full_all_features.CATPart'),
                        'body_index':candidate['source_body_index'],'body_name':candidate['source_body_name'],'output_path':str(output)}})
                    if result.isError:row['error']=result.model_dump_json()
                if output.exists():
                    measured=json.loads(output.read_text(encoding='utf-8'));row['live_source']=measured
                    row['comparison']=compare_geometry_features(objects[target['shape_id']],measured)
                rows.append(row);print(json.dumps({'shape_id':target['shape_id'],'checks':row.get('comparison',{}).get('checks'),'error':row.get('error')},ensure_ascii=False),flush=True)
                atomic_json(run/'shape-review/live-candidate-audit.json',{'rows':rows,'source_modified':False,'mapping_promoted':False})
if __name__=='__main__':asyncio.run(main())
