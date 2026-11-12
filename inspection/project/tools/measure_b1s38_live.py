"""Read exact source Body identity and SPA through this package's MCP."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[2]
async def main():
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/start_mcp.py')],cwd=str(ROOT),env=dict(os.environ,PYTHONIOENCODING='utf-8',CATIA_AGENT_MODE='full'))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            for name,args in [('catia_connect',{}),('catia_dev_dispatch',{'operation':'read_body_spa_identity','arguments':{
                'document_name':'full_all_features.CATPart','document_path':str(ROOT.parent/'full_all_features.CATPart'),
                'body_index':3,'body_name':'BREP_WITH_VOIDS #3067',
                'output_path':str(ROOT/'project/output/monitor/full-bulk-20261001-01/shape-review/b1s38-live-spa.json')}})]:
                result=await session.call_tool(name,args)
                print(result.model_dump_json(),flush=True)
                if result.isError:raise RuntimeError('MCP measurement failed')
if __name__=='__main__':asyncio.run(main())
