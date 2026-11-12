"""Current UI and current worker share a single run directory."""
import sys,os,json,time,threading,subprocess,argparse
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'project'),str(ROOT/'project/tools')]
import monitor_check as m
ASSETS=ROOT/'project/tools/current/fresh40-ui'
m.PAGE=ASSETS/'dashboard.html';m.__file__=str(ASSETS/'monitor_check.py')
p=argparse.ArgumentParser();p.add_argument('--run-directory',type=Path);p.add_argument('--center',type=float,nargs=3);p.add_argument('--half-size',type=float);p.add_argument('--target-bodies',type=int,default=40);p.add_argument('--clearance',type=float,default=.1);p.add_argument('--workers',type=int,default=8);p.add_argument('--no-browser',action='store_true');p.add_argument('--auto-start',action='store_true');args=p.parse_args()
if not 1<=args.workers<=32 or not 1<=args.target_bodies<=500 or args.clearance<0 or (args.half_size is not None and args.half_size<=0):p.error('参数超出允许范围')
directory=(args.run_directory or ROOT/'runs'/datetime.now().strftime('RUN-%Y%m%d-%H%M%S-%f')).resolve();directory.mkdir(parents=True,exist_ok=True)
if not (directory/'run-config.json').exists():
 (directory/'run-config.json').write_text(json.dumps({'center_mm':args.center,'half_size_mm':args.half_size,'target_bodies':args.target_bodies,'clearance_mm':args.clearance,'workers':args.workers},ensure_ascii=False,indent=2),encoding='utf8')
current_monitor=None
class CurrentMonitor(m.Monitor):
 def __init__(self,*a,**kw):
  global current_monitor
  current_monitor=self
  super().__init__(*a,**kw);self.watch_checkpoint=self.directory/'checkpoint.json';self.result=self.directory/'check.json'
  if self.result.exists():
   self.status='COMPLETE'
   started=m.read_json(self.directory/'run-started.json',{}) or {}
   if started.get('started'):self.started=datetime.fromisoformat(started['started']).timestamp()
 def start(self,workers=8,budget_minutes=60):
  if self.task_alive():raise ValueError('检查正在运行')
  if self.result.exists():raise ValueError('当前目录已有结果；重新检查请重新启动入口创建新目录。')
  config=json.loads((self.directory/'run-config.json').read_text(encoding='utf8'));config['workers']=max(1,min(32,int(workers)));(self.directory/'run-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
  self.status='RUNNING';self.started=time.time();self.event({'stage':'RUN_START','operation':'当前模型新一轮检查','max_workers':config['workers']})
  self.process=subprocess.Popen([sys.executable,str(ROOT/'scripts/current_run.py'),'--run-directory',str(self.directory)],cwd=ROOT,env=dict(os.environ,PYTHONIOENCODING='utf-8'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace')
  threading.Thread(target=self.read,daemon=True).start()
 def snapshot(self):
  value=super().snapshot();check=m.read_json(self.directory/'check.json',{}) or {};value['swept_route_review']=check.get('swept_route_review',{})
  value['run_config']=m.read_json(self.directory/'run-config.json',{}) or {}
  end=next((e for e in reversed(self.events) if e.get('stage')=='RUN_END'),None)
  if end is None:
   completed=m.read_json(self.directory/'run-completed.json',{}) or {}
   if completed.get('completed'):end={'time':completed['completed']}
  if end and self.status in ('COMPLETE','ERROR'):value['elapsed_seconds']=round(datetime.fromisoformat(end['time']).timestamp()-self.started)
  return value
m.Monitor=CurrentMonitor
native=m.ThreadingHTTPServer
def server(address,handler):
 class Downloads(handler):
  def do_POST(self):
   if self.path.endswith('/start'):
    info=m.read_json(directory/'monitor.json',{}) or {};prefix=info.get('url','').split('127.0.0.1:',1)[-1].partition('/')[2]
    if self.path!='/'+prefix+'start':self.send(b'{}',status=404);return
    if self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')):self.send(b'{}',status=403);return
    try:
     length=int(self.headers.get('Content-Length','0'))
     if length>1024:raise ValueError('请求过大')
     options=json.loads(self.rfile.read(length) or b'{}');config=m.read_json(directory/'run-config.json',{}) or {}
     if (directory/'check.json').exists():raise ValueError('当前已有结果；新检查请重新打开检查入口。')
     for key in ('center_mm','target_bodies','half_size_mm','clearance_mm'):
      if key in options:config[key]=options[key]
     if not 1<=int(config['target_bodies'])<=500 or float(config['clearance_mm'])<0:raise ValueError('范围或净距无效')
     if config.get('center_mm') is not None and (len(config['center_mm'])!=3 or not all(__import__('math').isfinite(float(x)) for x in config['center_mm'])):raise ValueError('中心坐标无效')
     if config.get('half_size_mm') is not None and config['half_size_mm']<=0:raise ValueError('半边长必须大于零')
     if self.server.current_monitor.task_alive():raise ValueError('检查正在运行')
     (directory/'run-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
     self.server.current_monitor.start(options.get('workers',8),options.get('budget_minutes',60));self.send(b'{"ok":true}');return
    except Exception as e:self.send(json.dumps({'error':str(e)},ensure_ascii=False).encode(),status=400);return
   super().do_POST()
  def do_GET(self):
   name=self.path.split('?')[0].rsplit('/',1)[-1]
   if name in ('report.pdf','report.docx','screenshots.zip'):
    # Validate token through the monitor's generated URL.
    info=m.read_json(directory/'monitor.json',{}) or {};prefix=info.get('url','').split('127.0.0.1:',1)[-1].partition('/')[2]
    if self.path.split('?')[0]!='/'+prefix+name:self.send(b'{}',status=404);return
    path=directory/name
    if not path.exists():self.send(b'{}',status=404);return
    self.send(path.read_bytes(),{'pdf':'application/pdf','docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','zip':'application/zip'}[path.suffix[1:]]);return
   super().do_GET()
 result=native(address,Downloads);result.current_monitor=current_monitor;return result
m.ThreadingHTTPServer=server
sys.argv=[sys.argv[0],'--run-directory',str(directory),'--workers',str(args.workers)]+(['--no-browser'] if args.no_browser else [])+(['--auto-start'] if args.auto_start else [])
m.main()
