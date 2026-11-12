"""Read-only local progress monitor for the active native CATIA run."""
import json,time,ctypes,mimetypes
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,unquote
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/全量原生DMU检查_20261012'
PAGE=ROOT/'tools/native-live-progress.html'
CACHE={}
def read_json(name):
 p=OUT/name
 try:
  stamp=p.stat().st_mtime_ns
  if name in CACHE and CACHE[name][0]==stamp:return CACHE[name][1]
  value=json.loads(p.read_text(encoding='utf-8-sig'));CACHE[name]=(stamp,value);return value
 except (OSError,ValueError):return CACHE.get(name,(None,{}))[1]
def tail(name):
 try:
  with (OUT/name).open('rb') as f:
   f.seek(0,2);f.seek(max(0,f.tell()-14000));return f.read().decode('utf8',errors='replace').splitlines()[-12:]
 except OSError:return []
def alive(pid):
 handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
 if not handle:return False
 code=ctypes.c_ulong();ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code));ctypes.windll.kernel32.CloseHandle(handle);return code.value==259
def state():
 review=read_json('native-gsd-spa-review.json');native=read_json('native-results.json');prep=read_json('preparation-audit.json');audit=read_json('capture-audit.json')
 rows=review.get('rows',[]);total=len(native.get('conflicts',[]));logs=tail('native-review.log');capturelogs=tail('centered-capture.log');errors=tail('centered-capture-error.log')
 capture_run=read_json('capture-run.json')
 fresh=(OUT/'capture-audit.json').exists() and (OUT/'capture-audit.json').stat().st_mtime>capture_run.get('started_epoch',time.time())
 jobs=audit.get('jobs',[]) if fresh else []
 if not fresh and capture_run.get('mode')=='batch':
  accepted=read_json('capture-pilot-accepted.json').get('issue_ids',[]);jobs=[j for j in audit.get('jobs',[]) if j.get('issue_id') in accepted]
 last=(jobs or audit.get('jobs',[]))[-1:]
 preview=None
 if last:
  job=last[0];preview={'id':job.get('issue_id'),'fresh':bool(jobs),'status':job.get('status'),'images':{}}
  for kind in ('context','detail'):
   p=Path(job.get(kind,{}).get('annotated',''))
   if p.is_file() and p.is_relative_to(OUT):preview['images'][kind]='/evidence/'+p.relative_to(OUT).as_posix()+'?v='+str(p.stat().st_mtime_ns)
 single=read_json('single-part-progress.json')
 running=alive(single.get('pid',27852));queued=alive(24900)
 phase='SPA / GSD 复核中' if running else ('截图试跑中' if queued and review.get('complete') else ('等待截图' if queued else ('截图试跑结束，等待图片验收' if jobs else '任务进程已停止，请检查日志')))
 result={'phase':phase,'time':time.strftime('%H:%M:%S'),'review':{'done':len(rows),'total':total,'complete':review.get('complete',False),'spa_errors':sum(r.get('spa',{}).get('status')=='ERROR' for r in rows),'gsd_errors':sum(r.get('gsd',{}).get('status')=='ERROR' for r in rows),'gsd_done':sum(r.get('gsd',{}).get('status')=='COMPLETE' for r in rows)},'native':{'total':total,'counts':{k:sum(r.get('type')==k for r in native.get('conflicts',[])) for k in ('CLASH','CONTACT','CLEARANCE')}},'prep':{'copied':len(prep.get('records',[])),'unresolved':len(prep.get('errors',[]))},'capture':{'done':len(jobs),'total':total,'pilot_total':2,'needs_review':sum(j.get('status')!='OK' for j in jobs),'restored':audit.get('restored') if fresh else None},'preview':preview,'logs':logs+capturelogs,'errors':errors}
 if single:
  result['phase']={'COPYING_FULL_PART':'一次性复制完整零件中','RESUMING_DIRECT_REVIEW':'恢复单零件复核中','DIRECT_GSD_REVIEW':'GSD 在完整零件副本内直接复核','COMPLETE':'单零件复核完成，等待截图','ERROR':'单零件复核异常，请查看日志'}.get(single.get('stage'),'准备单零件复核')
  if not running and not single.get('complete') and single.get('stage')!='ERROR':result['phase']='单零件任务停止，请查看日志'
  result['review'].update(done=single.get('done',0),total=single.get('total',0),complete=single.get('complete',False),gsd_done=single.get('gsd_done',0),gsd_errors=single.get('gsd_errors',0),mode='single')
  resumed=(OUT/'single-part-resume.log').exists()
  result['logs']=tail('single-part-resume.log' if resumed else 'single-part-review.log')+capturelogs;result['errors']=tail('single-part-resume-error.log' if resumed else 'single-part-review-error.log')+errors
 if capture_run and alive(capture_run.get('pid',0)):result['phase']='居中双视图批量截图中' if capture_run.get('mode')=='batch' else '居中双视图试截中'
 elif fresh and errors:result['phase']='截图中断，显示已恢复；正在修复'
 elif fresh and audit.get('restored') and jobs:result['phase']='试截完成，等待图片验收'
 incident=read_json('capture-incident.json')
 if incident.get('pid')==capture_run.get('pid') and alive(capture_run.get('pid',0)):result['phase']=incident.get('phase',result['phase'])
 scope=read_json('report-scope.json')
 if scope:
  result['capture']['total']=scope['selected_count']
  result['scope']={'selected':scope['selected_count'],'minimum_depth_mm':scope['minimum_depth_mm']}
 result['capture']['mode']=capture_run.get('mode','pilot')
 result['review']['spa_complete']=sum(r.get('spa',{}).get('status')=='COMPLETE' for r in rows)
 return result
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  route=unquote(urlparse(self.path).path)
  if route=='/api/status':
   data=json.dumps(state(),ensure_ascii=False).encode();mime='application/json; charset=utf-8'
  elif route=='/':data=PAGE.read_bytes();mime='text/html; charset=utf-8'
  elif route.startswith('/evidence/'):
   path=(OUT/route[len('/evidence/'):]).resolve()
   if not path.is_relative_to((OUT/'evidence').resolve()) or not path.is_file():self.send_error(404);return
   data=path.read_bytes();mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
