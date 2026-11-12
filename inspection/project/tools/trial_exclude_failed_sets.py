"""Invoke the explicit scope-derivative MCP operation against a saved baseline."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]

async def run(args):
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    source = baseline['active_document']
    part = baseline['parts'][source]
    names = [g['name'] for g in part['geometrical_sets'] if g['name'].startswith('面失败#')]
    env = dict(os.environ, PYTHONPATH=str(ROOT/'vendor/catia-v5-mcp-server'), PYTHONIOENCODING='utf-8')
    params = StdioServerParameters(command=sys.executable, args=['-m','catia_mcp.server'], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=__import__('datetime').timedelta(minutes=30)) as session:
            await session.initialize()
            await session.call_tool('catia_connect', {})
            await session.call_tool('catia_activate_document', {'name':source})
            result = await session.call_tool('catia_export_scope_derivative', {
                'source_name':source, 'excluded_set_names':names,
                'file_path':str(args.output.resolve()), 'audit_path':str(args.audit.resolve())})
            for item in result.content:
                if getattr(item,'text',None):
                    print(item.text[:1000], flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True)
    asyncio.run(run(parser.parse_args()))
