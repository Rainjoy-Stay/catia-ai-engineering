import json,time,ctypes
from pathlib import Path
f=Path('output/全量原生DMU检查_20261012');last=None
for n in range(240):
 try:
  run=json.loads((f/'capture-run.json').read_text(encoding='utf-8-sig'));a=json.loads((f/'capture-audit.json').read_text(encoding='utf8'))
  pid=run['pid'];h=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid);alive=False
  if h:
   code=ctypes.c_ulong();ctypes.windll.kernel32.GetExitCodeProcess(h,ctypes.byref(code));alive=code.value==259;ctypes.windll.kernel32.CloseHandle(h)
  state=dict(pid=pid,alive=alive,jobs=len(a['jobs']),restored=a.get('restored'),needs_review=sum(j['status']!='OK' for j in a['jobs']))
  if state!=last:
   with (f/'continuous-monitor.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps(dict(epoch=int(time.time()),**state))+'\n')
   last=state
 except Exception:pass
 time.sleep(15)
