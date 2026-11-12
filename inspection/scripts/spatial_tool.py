"""Structured MCP bridge to the same offline spatial UI/worker."""
import json,os,sys,subprocess,time
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
class SpatialTool:
 def get_tool_definitions(self):
  return [{'name':'catia_open_spatial_inspection_ui','description':'Open the current offline spatial inspection UI for the active CATPart. Includes solids and finite surfaces/shells; fresh run, no historical geometry. Optional auto_start launches read-only export and calculation. Returns actual local URL and run directory.','inputSchema':{'type':'object','properties':{'center_mm':{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3},'half_size_mm':{'type':'number','exclusiveMinimum':0},'target_bodies':{'type':'integer','minimum':1,'maximum':500,'default':40},'clearance_mm':{'type':'number','minimum':0,'default':.1},'workers':{'type':'integer','minimum':1,'maximum':32,'default':8},'auto_start':{'type':'boolean','default':False}},'additionalProperties':False}},
   {'name':'catia_get_spatial_inspection_result','description':'Read the current run results, progress and delivery status without changing geometry or decisions. Run directory must be inside this package runs directory.','inputSchema':{'type':'object','properties':{'run_directory':{'type':'string'}},'required':['run_directory'],'additionalProperties':False}}]
 def execute(self,name,args):
  return json.dumps(self._execute(name,args),ensure_ascii=False,default=str)
 def _execute(self,name,args):
  if name=='catia_open_spatial_inspection_ui':
   folder=ROOT/'runs'/datetime.now().strftime('RUN-%Y%m%d-%H%M%S-%f');folder.mkdir(parents=True)
   cmd=[sys.executable,'-X','utf8',str(ROOT/'scripts/current_ui.py'),'--run-directory',str(folder),'--target-bodies',str(args.get('target_bodies',40)),'--clearance',str(args.get('clearance_mm',.1)),'--workers',str(args.get('workers',8))]
   if args.get('center_mm') is not None:cmd+=['--center',*map(str,args['center_mm'])]
   if args.get('half_size_mm') is not None:cmd+=['--half-size',str(args['half_size_mm'])]
   if args.get('auto_start'):cmd+=['--auto-start']
   with (folder/'ui-start.log').open('w',encoding='utf8') as log:
    process=subprocess.Popen(cmd,cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1'),stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   for _ in range(100):
    if (folder/'monitor.json').exists():return {'run_directory':str(folder),**json.loads((folder/'monitor.json').read_text(encoding='utf8'))}
    if process.poll() is not None:raise RuntimeError('UI 启动失败，查看 '+str(folder/'ui-start.log'))
    time.sleep(.1)
   return {'run_directory':str(folder),'pid':process.pid,'status':'STARTING','log':str(folder/'ui-start.log')}
  folder=Path(args['run_directory']).resolve();folder.relative_to((ROOT/'runs').resolve())
  value={'run_directory':str(folder)}
  for n in ['run-config.json','check.json','delivery.json','monitor.json']:
   if (folder/n).exists():value[n]=json.loads((folder/n).read_text(encoding='utf8'))
  return value
