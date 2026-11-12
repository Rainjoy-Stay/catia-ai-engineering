import argparse, json
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--base-url'); p.add_argument('--model'); p.add_argument('--template',action='store_true')
a=p.parse_args()
path=ROOT/'project/config/runtime.json'; cfg=json.loads(path.read_text(encoding='utf-8'))
if a.base_url:
    url=urlparse(a.base_url)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:
        p.error('Supply a credential-free http(s) API base URL.')
    if not a.model: p.error('--model must be the exact API model ID')
    cfg['llm'].update(mode='openai_compatible_intranet',base_url=a.base_url.rstrip('/'),model=a.model)
    cfg['deployment'].update(api_base_url_confirmed=True,model_id_confirmed=True)
if a.template: cfg['llm']['mode']='template'
path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
mc={'mcpServers':{'catia-v5r18-checker':{'command':str(ROOT/'runtime/python.exe'),'args':[str(ROOT/'scripts/start_mcp.py')],'env':{'PYTHONUTF8':'1'}}}}
(ROOT/'Deepseek-Harness-MCP.json').write_text(json.dumps(mc,ensure_ascii=False,indent=2),encoding='utf-8')
print('MCP config generated. LLM mode:',cfg['llm']['mode'])
