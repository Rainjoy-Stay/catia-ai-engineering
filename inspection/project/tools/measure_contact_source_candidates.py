"""Read three exact CATIA surface identities through the structured MCP server."""
import asyncio, json, os, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT = Path(__file__).resolve().parents[2]

async def main():
    run = ROOT/'project/output/monitor/full-bulk-20261001-01'
    params = StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/start_mcp.py')],
        cwd=str(ROOT),env=dict(os.environ,PYTHONIOENCODING='utf-8',CATIA_AGENT_MODE='full'))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize(); await session.call_tool('catia_connect',{})
            for index in (330,331,332):
                output = run/f'shape-review/native-surface-{index}.json'
                if output.exists():
                    print('EXISTING_EVIDENCE',index,flush=True); continue
                result = await session.call_tool('catia_dev_dispatch',{'operation':'read_surface_spa_identity','arguments':{
                    'document_name':'full_all_features.CATPart','document_path':str(ROOT.parent/'full_all_features.CATPart'),
                    'set_index':1,'set_name':'几何图形集.1','shape_index':index,
                    'shape_name':'BREP_WITH_VOIDS #3068','output_path':str(output)}})
                print(result.model_dump_json(),flush=True)
                if result.isError: raise RuntimeError('Native measurement failed')

if __name__ == '__main__': asyncio.run(main())
