import json,time,subprocess,ctypes,sys
from pathlib import Path
root=Path.cwd();f=root/'output/全量原生DMU检查_20261012'
pid=int(sys.argv[1]);kernel=ctypes.windll.kernel32
h=kernel.OpenProcess(0x100000,False,pid)
if h:
 kernel.WaitForSingleObject(h,0xFFFFFFFF);kernel.CloseHandle(h)
a=json.loads((f/'capture-audit.json').read_text(encoding='utf8'))
if not a.get('restored') or len(a['jobs'])!=168:raise RuntimeError('Recovery incomplete')
script=root/'output/原生DMU方案验证_20261012/full_native_capture.py'
p=subprocess.Popen([sys.executable,str(script),'--repair','--repair-limit=4'],stdout=(f/'bulk-pilot.stdout.log').open('w'),stderr=(f/'bulk-pilot.stderr.log').open('w'),creationflags=0x08000000)
(f/'capture-run.json').write_text(json.dumps(dict(repair=True,mode='bulk-selection-pilot',total=168,pilot_limit=4,pid=p.pid,started_epoch=int(time.time()))),encoding='utf8')
