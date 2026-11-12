import sys,time,json,subprocess
from pathlib import Path
root=Path.cwd();f=root/'output/全量原生DMU检查_20261012'
sys.path.insert(0,str(root/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection
c=CATIAConnection()
for n in range(30):
 try:c.connect();break
 except Exception:time.sleep(2)
app=c.app;app.Visible=True
print('OPENING_SAVED_ASSEMBLY',flush=True)
doc=app.Documents.Open(str(f/'NativeDMU_Full_20261012.CATProduct'));doc.Activate()
print('OPENED',doc.Product.Products.Count,flush=True)
a=json.loads((f/'capture-audit.json').read_text(encoding='utf8'))
b=json.loads((f/'capture-audit-before-resume-pilot.json').read_text(encoding='utf8'))
merged={j['issue_id']:j for j in b['jobs']};merged.update({j['issue_id']:j for j in a['jobs']})
a['jobs']=[merged[k] for k in sorted(merged)];a['restored']=False;a['reopened_from_saved_model']=True
(f/'capture-audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf8')
# Reuse accepted images after a model reopen, without claiming display recovery.
script=root/'output/原生DMU方案验证_20261012/full_native_capture.py'
p=subprocess.Popen([sys.executable,str(script),'--repair','--repair-limit=4'],stdout=(f/'bulk-pilot.stdout.log').open('w'),stderr=(f/'bulk-pilot.stderr.log').open('w'),creationflags=0x08000000)
(f/'capture-run.json').write_text(json.dumps(dict(repair=True,mode='bulk-selection-pilot',total=168,pilot_limit=4,pid=p.pid,started_epoch=int(time.time()))),encoding='utf8')
print('BULK_PILOT_STARTED',p.pid,flush=True)
