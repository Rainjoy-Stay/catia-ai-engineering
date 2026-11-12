import argparse, importlib, json, platform, struct, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--catia',action='store_true'); a=p.parse_args()
root=Path(__file__).resolve().parents[1]
checks=[]
def run(name,fn):
    try: result=fn(); checks.append({'check':name,'status':'PASS','detail':str(result)})
    except Exception as exc: checks.append({'check':name,'status':'FAIL','detail':str(exc)})
def platform_check():
    assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8
    assert platform.system()=='Windows'
    return platform.platform()
run('Python 3.12 Windows x64',platform_check)
for mod in ['pythoncom','win32com.client','mcp','docx','PIL','catia_checker','catia_mcp']:
    run('import '+mod,lambda mod=mod: importlib.import_module(mod).__file__)
def tests():
    cp=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root/'project/tests'),'-v'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (root/'validation/unit-tests.txt').write_text(cp.stdout+cp.stderr,encoding='utf-8')
    if cp.returncode: raise RuntimeError('Unit tests failed; see unit-tests.txt')
    return cp.stderr.strip().splitlines()[-1]
run('offline rule tests',tests)
def active_rules():
    from catia_checker.routing_rules import validate_rules
    rules=json.loads((root/'project/config/rules-active.json').read_text(encoding='utf-8'))
    validate_rules(rules)
    return rules['ruleset_id']
run('active rules validation',active_rules)
from start_mcp import make_server, ALLOWED
run('MCP merged tool exposure',lambda: sorted(make_server()._tool_router))
if a.catia:
    from r18_connection import V5Connection
    conn=V5Connection()
    def probe():
        try: return conn.connect()
        finally: conn.disconnect()
    run('Live CATIA V5 attachment and release detection',probe)
else: checks.append({'check':'Live CATIA V5 geometry and license acceptance','status':'NOT_TESTED'})
result={
    'checks':checks,
    'development_environment':{'product':'CATIA P3 V5-6R2022','release':'32','live_validated':bool(a.catia)},
    'intranet_target_environment':{'product':'CATIA V5 R30','release':'30','live_validated':False},
    'live_geometry_validated':False,
}
(root/'validation/self-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(any(c['status']=='FAIL' for c in checks))
