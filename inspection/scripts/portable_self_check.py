"""Offline deployment checks, with explicit live-CATIA separation."""
import sys,json,importlib,subprocess,platform,struct,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'project'),str(ROOT/'scripts')]
p=argparse.ArgumentParser();p.add_argument('--catia',action='store_true');p.add_argument('--tests',action='store_true');p.add_argument('--hashes',action='store_true');args=p.parse_args();rows=[]
def check(name,fn):
 try:rows.append({'check':name,'status':'PASS','detail':str(fn())})
 except Exception as e:rows.append({'check':name,'status':'FAIL','detail':str(e)})
def runtime():
 assert platform.system()=='Windows' and sys.version_info[:2]==(3,12) and struct.calcsize('P')==8
 return sys.executable
check('离线 Python 3.12 x64',runtime)
for mod in ['pythoncom','win32com.client','mcp','OCP','numpy','PIL','docx','reportlab','pymupdf','yaml','catia_checker','catia_mcp']:
 check('依赖 '+mod,lambda mod=mod:importlib.import_module(mod).__file__)
def rules():
 from catia_checker.routing_rules import validate_rules
 value=json.loads((ROOT/'project/config/rules-active.json').read_text(encoding='utf8'));validate_rules(value);return value['ruleset_id']
check('规则配置',rules)
def mcp():
 import start_mcp
 server=start_mcp.make_server();return {'tool_count':len(server._tool_router),'mode':'full'}
check('MCP 工具注册',mcp)
if args.tests:
 def tests():
  cp=subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s',str(ROOT/'project/tests'),'-v'],capture_output=True,text=True,encoding='utf8',errors='replace',cwd=ROOT)
  (ROOT/'validation/unit-tests.txt').write_text(cp.stdout+cp.stderr,encoding='utf8')
  if cp.returncode:raise RuntimeError('回归失败，见 validation/unit-tests.txt')
  return cp.stderr.splitlines()[-3:]
 check('离线回归',tests)
if args.catia:
 def catia():
  from r18_connection import R18Connection
  c=R18Connection()
  try:return c.connect()
  finally:c.disconnect()
 check('本机 CATIA 连接与版本',catia)
else:rows.append({'check':'内网 CATIA R30 与许可现场验收','status':'NOT_TESTED'})
if args.hashes:
 def hashes():
  manifest=json.loads((ROOT/'file-manifest.json').read_text(encoding='utf8'));errors=[]
  for name,expected in manifest.items():
   path=ROOT/name
   if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append(name)
  if errors:raise RuntimeError('文件缺失或被修改：'+str(errors[:20]))
  return len(manifest)
 check('发布文件哈希',hashes)
result={'package':'CATIA_Offline_20261012','checks':rows,'passed':not any(r['status']=='FAIL' for r in rows)}
(ROOT/'validation').mkdir(exist_ok=True);(ROOT/'validation/portable-self-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(not result['passed'])
