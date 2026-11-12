"""Local live inspection dashboard. No external services or browser dependencies."""
from __future__ import annotations
import argparse, json, os, secrets, subprocess, sys, threading, time, webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from monitor_data import dashboard_data, read_json

ROOT = Path(__file__).resolve().parents[2]
PAGE = Path(__file__).with_name('dashboard.html')

def process_alive(pid):
    if not pid:return False
    # QUERY_LIMITED_INFORMATION only: never suspend or terminate the worker.
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return False
    try:
        code=wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
    finally:kernel.CloseHandle(handle)

class Monitor:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.events = []
        self.process = None
        self.started = time.time()
        self.status = 'READY'
        self.result = directory / 'check.json'
        self.watch_checkpoint = None
        self.watch_pid = None
        self.watch_events = None
        self.fallback_report = None
        self.direct_source = None
        self.full_bulk = False
        self.control_existing = False

    def task_alive(self):
        return self.process.poll() is None if self.process else process_alive(self.watch_pid)

    def bulk_ready(self):
        try:return json.loads((self.directory/'export-audit.json').read_text(encoding='utf-8')).get('status')=='EXPORTED'
        except (OSError,ValueError):return False

    def resident_info(self):
        try:
            value=json.loads((self.directory/'resident-state.json').read_text(encoding='utf-8'))
            pid=self.process.pid if self.process else self.watch_pid
            return value if value.get('pid')==pid and self.task_alive() else {}
        except (OSError,ValueError):return {}

    def pause(self):
        with self.lock:
            if self.status!='RUNNING' or not self.task_alive():
                raise ValueError('当前没有可暂停的受控检查')
            if not self.direct_source and not (self.full_bulk and self.bulk_ready()):raise ValueError('CATIA 导出阶段不能安全暂停；进入精算后可暂停')
            self.status='PAUSING'
            (self.directory/'pause-request.json').write_text('{}',encoding='utf-8')
        self.event({'stage':'PAUSE_REQUEST','operation':'暂停请求：当前计算结束后保存检查点'})

    def event(self, value):
        value = dict(value, time=datetime.now().isoformat(timespec='seconds'))
        with self.lock:
            if value.get('stage')=='PAUSED' and value.get('resident'):self.status='PAUSED'
            elif value.get('stage')=='RESIDENT_RESUMED':self.status='RUNNING'
            self.events.append(value)
            with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(value, ensure_ascii=False) + '\n')

    def start(self, workers=8, budget_minutes=60):
        workers=int(workers); budget_minutes=int(budget_minutes)
        if not 1<=workers<=min(32,os.cpu_count() or 1):
            raise ValueError('并发数超出本机范围')
        if not 1<=budget_minutes<=240:
            raise ValueError('计算预算必须为 1—240 分钟')
        resident=self.resident_info()
        if self.status=='PAUSED' and resident.get('status')=='PAUSED':
            from run_full_bulk_check import load_completed_export
            from catia_checker.occt_session_cache import atomic_json
            load_completed_export(self.directory,'full_all_features.CATPart')
            with self.lock:
                if self.status!='PAUSED':raise ValueError('任务状态已变化')
                atomic_json(self.directory/'resume-settings.json',{'workers':workers,'budget_minutes':budget_minutes})
                self.status='RUNNING'
                (self.directory/'pause-request.json').unlink(missing_ok=True)
            self.event({'stage':'RESUME_REQUEST','max_workers':workers,'operation':'恢复内存中 OCCT 会话；不重新导入或生成网格'})
            return
        with self.lock:
            if self.status in ('RUNNING','PAUSING') or (self.control_existing and self.task_alive()):
                raise ValueError('检查正在运行')
            self.status = 'RUNNING'
            self.events = []
            self.watch_events = None
        self.started = time.time()
        checkpoint=self.watch_checkpoint or self.directory/'checkpoint.json'
        self.watch_checkpoint=checkpoint
        self.result=self.directory/f'check-{datetime.now():%Y%m%d-%H%M%S}.json'
        command = [sys.executable, str(ROOT/'project/tools/inspect_active_large_single_part_batched.py'),
                   '--output', str(self.result), '--checkpoint', str(checkpoint),
                   '--timeout', str(budget_minutes*60+3600), '--run-budget', str(budget_minutes*60),
                   '--workers',str(workers)]
        if self.direct_source:
            (self.directory/'pause-request.json').unlink(missing_ok=True)
            self.result=self.directory/'check.json'
            command=[sys.executable,str(ROOT/'project/tools/run_direct_step_check.py'),str(self.direct_source),
                     '--directory',str(self.directory),'--resume','--workers',str(workers),
                     '--budget-minutes',str(budget_minutes)]
        if self.full_bulk:
            command=[sys.executable,str(ROOT/'project/tools/run_full_bulk_check.py'),
                     '--directory',str(self.directory),'--workers',str(workers)]
            if self.bulk_ready():
                command.extend(['--resume-check','--budget-minutes',str(budget_minutes)])
                (self.directory/'pause-request.json').unlink(missing_ok=True)
            elif (self.directory/'export-audit.json').exists():
                command.append('--resume-export')
            self.result=self.directory/'check.json'
        env = dict(os.environ, PYTHONIOENCODING='utf-8', CATIA_MONITOR_DIRECTORY=str(self.directory))
        if self.full_bulk:env['CATIA_OCCT_KEEP_RESIDENT']='1'
        if self.direct_source:env['CATIA_MONITOR_MANAGED']='1'
        self.process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        self.event({'stage':'RUN_START', 'operation':f'并发 {workers}；本轮 STEP 检查点续跑' if self.direct_source else f'并发 {workers}；续跑检查点；只读临时导出 Body', 'max_workers':workers,'budget_minutes':budget_minutes,'source_saved_by_tool':False})
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.process.stdout:
            try: value = json.loads(line)
            except ValueError: value = {'stage':'MESSAGE', 'message':line.strip()}
            if isinstance(value, dict): self.event(value)
        code = self.process.wait()
        self.status = 'COMPLETE' if code == 0 else 'PAUSED' if code==2 else 'ERROR'
        self.event({'stage':'RUN_END', 'exit_code':code})

    def snapshot(self):
        if self.watch_events:
            try:
                all_events=[]
                for line in self.watch_events.read_text(encoding='utf-8').splitlines():
                    try: value=json.loads(line)
                    except ValueError:continue
                    if value.get('stage')=='RUN_START':all_events=[]
                    all_events.append(value)
                self.events=all_events
                if all_events:
                    self.started=datetime.fromisoformat(all_events[0]['time']).timestamp()
                ends=[e for e in all_events if e.get('stage')=='RUN_END']
                if ends:
                    code=ends[-1].get('exit_code')
                    self.status='PAUSED' if code==2 or (code==0 and (self.directory/'pause-request.json').exists()) else 'COMPLETE' if code==0 else 'ERROR'
                elif self.control_existing:
                    if self.resident_info().get('status')=='PAUSED':self.status='PAUSED'
                    elif (self.directory/'pause-request.json').exists():self.status='PAUSING' if self.task_alive() else 'PAUSED'
                    elif self.task_alive():self.status='RUNNING'
                    else:self.status='ERROR'
            except OSError:pass
        with self.lock:
            events = self.events[-500:]
            completed = [e for e in self.events if e.get('stage','').startswith('EXACT_PAIR_') and e.get('stage','').endswith('_COMPLETE')]
            totals = {'completed':sum(e.get('status')=='COMPLETE' for e in completed),
                      'timeouts':sum(e.get('status')=='TIMEOUT' for e in completed),
                      'errors':sum(e.get('status')=='ERROR' for e in completed), 'attempts':len(completed)}
        payload = {'status':self.status, 'elapsed_seconds':round(time.time()-self.started), 'events':events,
                   'totals':totals, 'pause_supported':bool(self.direct_source or (self.full_bulk and self.bulk_ready())),
                   'result_path':str(self.result), 'preview_ready':(self.directory/'preview.json').exists()}
        payload['watch_only']=bool(self.watch_events and not self.control_existing)
        payload['resident']=self.resident_info()
        payload['export_progress']=export_progress(self.directory)
        loads=[e for e in self.events if e.get('stage')=='BATCH_LOAD_START']
        payload['pipeline_counts']={'imported':sum(e.get('stage')=='BATCH_LOAD_COMPLETE' for e in self.events),
            'batch_total':loads[-1].get('batch_count',0) if loads else 0,
            'preview_complete':any(e.get('stage')=='PREVIEW_COMPLETE' for e in self.events)}
        payload['dashboard']=dashboard_data(self.directory,self.watch_checkpoint,
                                            self.result if self.result.exists() else self.fallback_report,self.events)
        payload['preview_version']=(self.directory/'preview.json').stat().st_mtime_ns if payload['preview_ready'] else None
        if self.watch_checkpoint and self.watch_checkpoint.exists():
            try:
                saved=json.loads(self.watch_checkpoint.read_text(encoding='utf-8'))
                payload['resume']={'completed_pairs':len(saved.get('completed_pairs',[]))}
            except (ValueError,OSError):pass
        if self.result.exists():
            try:
                result = read_json(self.result,{}) or {}
                if self.status not in ('PAUSED','PAUSING') and self.watch_checkpoint and not self.task_alive():
                    failed=bool(result.get('counts',{}).get('ERROR')) or bool(result.get('audit',{}).get('exceptions'))
                    self.status='ERROR' if failed else 'COMPLETE';payload['status']=self.status
                payload.update(counts=result.get('counts'),resume=result.get('resume_status'),source=result.get('source'))
            except (ValueError, OSError): pass
        return payload


def export_progress(directory):
    def read(name):
        try:return json.loads((directory/name).read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
    bodies=read('export-audit.json')
    coverage=read('surfaces/surface-export-coverage.json')
    receipts=read('surfaces/export-checkpoint.json').get('completed_batches',[])
    latest=receipts[-1] if receipts else {}
    path=directory/'surfaces/surface-export-coverage.json'
    return {'body_done':bodies.get('exported_body_count',0),'body_total':bodies.get('expected_body_count',0),
            'body_batches':len([r for r in bodies.get('batch_files',[]) if '/export/' in r.replace('\\','/')]),
            'surface_done':coverage.get('exported',0),'surface_total':coverage.get('registered',0),
            'surface_batches':len(receipts),'surface_errors':len(coverage.get('errors',[])),
            'latest_batch':latest.get('batch_id'),'latest_object':(latest.get('body_mapping') or [{}])[-1].get('source_path'),
            'updated_at':datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds') if path.exists() else None,
            'seconds_since_update':round(time.time()-path.stat().st_mtime) if path.exists() else None,
            'export_finished':bodies.get('status')=='EXPORTED'}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run-directory',type=Path); parser.add_argument('--watch-report',type=Path); parser.add_argument('--watch-checkpoint',type=Path); parser.add_argument('--watch-events',type=Path); parser.add_argument('--watch-pid',type=int); parser.add_argument('--fallback-report',type=Path); parser.add_argument('--no-browser',action='store_true'); parser.add_argument('--auto-start',action='store_true'); parser.add_argument('--workers',type=int,default=8); parser.add_argument('--budget-minutes',type=int,default=60); parser.add_argument('--direct-source',type=Path); parser.add_argument('--full-bulk',action='store_true'); args=parser.parse_args()
    directory=(args.run_directory or ROOT/'project/output/monitor'/datetime.now().strftime('%Y%m%d-%H%M%S')).resolve()
    monitor=Monitor(directory); token=os.environ.get('CATIA_MONITOR_TOKEN') or secrets.token_urlsafe(18)
    if not token.replace('-','').replace('_','').isalnum():raise ValueError('Invalid monitor URL token')
    monitor.full_bulk=args.full_bulk
    monitor.control_existing=os.environ.get('CATIA_MONITOR_ATTACH_CONTROL')=='1'
    if monitor.control_existing and not (args.full_bulk and args.watch_report and args.watch_pid and args.watch_events):
        raise ValueError('Attach control requires full-bulk run, report, exact PID and events')
    if args.direct_source:
        monitor.direct_source=args.direct_source.resolve()
        if not monitor.direct_source.is_file():raise ValueError('STEP source missing')
        monitor.watch_checkpoint=directory/'checkpoint.json'
        monitor.status='PAUSED'
        monitor.event({'stage':'PAUSED','operation':'已暂停；可调整并发并继续本轮 STEP 检查'})
    if args.watch_report:
        monitor.result=args.watch_report.resolve();monitor.watch_checkpoint=args.watch_checkpoint;monitor.status='RUNNING'
        monitor.watch_events=args.watch_events;monitor.watch_pid=args.watch_pid;monitor.fallback_report=args.fallback_report
        if not args.watch_events:monitor.event({'stage':'EXACT_PAIR_WATCH','operation':'监控现有检查点；本轮完整事件在原测试进程中'})
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self, body, content='application/json', status=200):
            self.send_response(status);self.send_header('Content-Type',content);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            route=self.path.split('?')[0]
            if route=='/'+token+'/human-review':
                try:
                    from human_review import read_round
                    self.send(json.dumps(read_round(directory),ensure_ascii=False).encode())
                except Exception as exc:self.send(json.dumps({'error':str(exc)}).encode(),status=400)
                return
            if route=='/'+token+'/human-review/image':
                try:
                    from urllib.parse import urlsplit,parse_qs
                    from human_review import image_path
                    query=parse_qs(urlsplit(self.path).query)
                    path=image_path(directory,query.get('case',[''])[0],query.get('image',[''])[0])
                    self.send(path.read_bytes(),'image/jpeg')
                except Exception as exc:self.send(json.dumps({'error':str(exc)}).encode(),status=404)
                return
            if route=='/'+token+'/attribution/object':
                from urllib.parse import urlsplit,parse_qs
                sid=parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                register=read_json(directory/'attribution-objects.json') or {}
                value=register.get(sid)
                self.send(json.dumps(value,ensure_ascii=False).encode(),status=200 if value else 404);return
            if route=='/'+token+'/original-retry':
                path=directory/'shape-review/original-retry-batch/summary.json'
                if not path.exists():self.send(b'{}',status=404);return
                value=read_json(path)
                value['process_alive']=process_alive(value.get('pid'))
                self.send(json.dumps(value,ensure_ascii=False).encode());return
            if route in ('/'+token,'/'+token+'/'):
                self.send(PAGE.read_bytes(),'text/html; charset=utf-8')
            elif route in ('/'+token+'/dashboard.js','/'+token+'/dashboard.css','/'+token+'/attribution-view.js','/'+token+'/human-review.js'):
                asset=Path(__file__).with_name(route.rsplit('/',1)[-1])
                self.send(asset.read_bytes(),'text/javascript; charset=utf-8' if asset.suffix=='.js' else 'text/css; charset=utf-8')
            elif route=='/'+token+'/state': self.send(json.dumps(monitor.snapshot(),ensure_ascii=False).encode())
            elif route=='/'+token+'/interference-review' and (directory/'interference-review.json').exists(): self.send((directory/'interference-review.json').read_bytes())
            elif route=='/'+token+'/preview' and (directory/'preview.json').exists(): self.send((directory/'preview.json').read_bytes())
            else:self.send(b'{}',status=404)
        def do_POST(self):
            if self.path not in ('/'+token+'/start','/'+token+'/pause','/'+token+'/attribution/revoke','/'+token+'/human-review/label'): self.send(b'{}',status=404);return
            if self.headers.get('Origin') not in (None, 'http://'+self.headers.get('Host','')):
                self.send(b'{}',status=403);return
            if monitor.watch_events and not monitor.control_existing and not self.path.endswith(('/attribution/revoke','/human-review/label')):
                self.send('{"error":"此页面仅监控已有任务，不会启动重复计算"}'.encode('utf-8'),status=409);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length>(16384 if self.path.endswith('/human-review/label') else 1024):raise ValueError('请求过大')
                options=json.loads(self.rfile.read(length) or b'{}')
                if self.path.endswith('/human-review/label'):
                    from human_review import save_label
                    self.send(json.dumps(save_label(directory,options),ensure_ascii=False).encode());return
                if self.path.endswith('/attribution/revoke'):
                    from monitor_data import revoke_attribution
                    outcome=revoke_attribution(directory,options.get('pair'),options.get('geometry_fingerprint'))
                    self.send(json.dumps(outcome).encode());return
                elif self.path.endswith('/pause'):monitor.pause()
                else:monitor.start(options.get('workers',8),options.get('budget_minutes',60))
                self.send(b'{"ok":true}')
            except Exception as exc:self.send(json.dumps({'error':str(exc)}).encode(),status=400)
    server=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('CATIA_MONITOR_PORT','0'))),Handler)
    url=f'http://127.0.0.1:{server.server_port}/{token}/'
    (directory/'monitor.json').write_text(json.dumps({'url':url,'pid':os.getpid()},indent=2),encoding='utf-8')
    print(url,flush=True)
    if args.auto_start:
        monitor.watch_checkpoint=args.watch_checkpoint
        monitor.fallback_report=args.fallback_report
        monitor.start(args.workers,args.budget_minutes)
    if not args.no_browser:webbrowser.open(url)
    server.serve_forever()


if __name__=='__main__':main()
