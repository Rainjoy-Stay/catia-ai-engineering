"""Inventory ten review targets and measure only verified source identities via MCP."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'project'))
from catia_checker.occt_session_cache import atomic_json

async def main():
    run=ROOT/'project/output/monitor/full-bulk-20261001-01'
    registry=json.loads((run/'registry.json').read_text(encoding='utf-8'))['objects']
    reviews=[]
    for path in ('shape-review/review.json','shape-review/round-2/review.json'):
        reviews.extend(json.loads((run/path).read_text(encoding='utf-8'))['rows'])
    rows=[]
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/start_mcp.py')],cwd=str(ROOT),env=dict(os.environ,PYTHONIOENCODING='utf-8',CATIA_AGENT_MODE='full'))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize();connection=await session.call_tool('catia_connect',{})
            for index,review in enumerate(reviews[:10]):
                objects=[registry[id] for id in review['pair']]
                row={'pair':review['pair'],'conversion_confirmed':False,'excluded':False,
                     'cache_input_valid':review['details']['input_valid'],
                     'source_objects':[{key:obj.get(key) for key in ('source_body_index','source_body_name','source_path','mapping_method','source_set_path','source_name')} for obj in objects]}
                if False in row['cache_input_valid']:
                    row.update(status='INVALID_INPUT_GEOMETRY',reason='缓存几何自交／不可定向；原始 STEP 实体定位失败，来源异常阶段尚未确认')
                elif not all(obj.get('mapping_method')=='MULTI_FEATURE_EXACT_ONE_TO_ONE' for obj in objects):
                    row.update(status='SOURCE_MAPPING_REQUIRED',reason='缺少双方独立 CATIA 元素一一映射，不能仅从复制标签认定来源相同')
                else:
                    output=run/f'shape-review/ten-pair-source-{index:02d}.json'
                    if not output.exists():
                        result=await session.call_tool('catia_dev_dispatch',{'operation':'read_exact_body_pair_distance','arguments':{
                            'document_name':'full_all_features.CATPart','document_path':str(ROOT.parent/'full_all_features.CATPart'),
                            'bodies':[{'index':o['source_body_index'],'name':o['source_body_name']} for o in objects], 'output_path':str(output)}})
                        if result.isError:row.update(status='SOURCE_MEASUREMENT_ERROR',reason=result.model_dump_json())
                    if output.exists():
                        row['source_measurement']=json.loads(output.read_text(encoding='utf-8'))
                        row.update(status='SOURCE_DISTANCE_MEASURED',reason='源模型距离已测量；零距离仍不能区分接触与穿透，不自动认定转换伪干涉')
                rows.append(row);print(json.dumps({'pair':row['pair'],'status':row['status']},ensure_ascii=False),flush=True)
    atomic_json(run/'shape-review/ten-pair-source-review.json',{'rows':rows,'source_modified':False,'formal_acceptance':False})

if __name__=='__main__':asyncio.run(main())
