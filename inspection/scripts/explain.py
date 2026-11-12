import argparse, json
from pathlib import Path
from catia_checker.llm_adapter import create_llm_adapter, load_runtime_config
p=argparse.ArgumentParser(); p.add_argument('input',type=Path); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
root=Path(__file__).resolve().parents[1]
response=create_llm_adapter(load_runtime_config(root/'project/config/runtime.json')).explain(json.loads(a.input.read_text(encoding='utf-8')))
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(response.text,encoding='utf-8')
a.output.with_suffix('.audit.json').write_text(json.dumps(response.audit,ensure_ascii=False,indent=2),encoding='utf-8')
print('provider=',response.provider,'degraded=',response.degraded)
