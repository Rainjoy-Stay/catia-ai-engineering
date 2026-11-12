"""Serve a dependency-free local result viewer with CATIA Body location."""
from __future__ import annotations
import argparse, html, json, os, secrets, sys, threading, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; PROJECT=ROOT/"project"
for value in (str(PROJECT),str(ROOT/"scripts")):
    if value not in sys.path: sys.path.insert(0,value)
from catia_checker.report_viewer import actionable_findings,find_default_report,finding_row
from catia_checker.result_locator import load_issue_target,location_capability,select_issue_target
from r18_connection import R18Connection

def render_page(report_path:Path,findings:list[dict],token:str)->bytes:
    rows=[]
    for finding in findings:
        status,severity,issue,title,objects,measured=finding_row(finding)
        cells="".join(f"<td>{html.escape(x)}</td>" for x in (status,severity,issue,title,objects,measured))
        capability=location_capability(finding); unavailable=capability["kind"]=="UNAVAILABLE"
        button=(f'<button disabled data-fixed-disabled="true" title="{html.escape(capability["reason"])}">不可定位</button>' if unavailable else f'<button onclick="locate({json.dumps(issue)})">在 CATIA 中定位</button>')
        rows.append(f'<tr><td>{button}</td>{cells}</tr>')
    page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>CATIA 检查结果与模型定位</title>
<style>body{{font-family:"Microsoft YaHei",sans-serif;margin:24px;color:#101828;background:#f7f8fa}}.card{{background:white;border:1px solid #e4e7ec;border-radius:12px;padding:18px;box-shadow:0 2px 8px #0000000d}}h1{{font-size:22px;margin:0 0 8px}}.path{{color:#667085;word-break:break-all;margin-bottom:16px}}#message{{min-height:24px;font-weight:600;color:#175cd3;margin:10px 0}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{border-bottom:1px solid #eaecf0;padding:10px;text-align:left}}th{{background:#f9fafb;position:sticky;top:0}}button{{background:#175cd3;color:white;border:0;border-radius:6px;padding:7px 11px;cursor:pointer}}button:disabled{{background:#98a2b3}}</style></head>
<body><div class="card"><h1>CATIA 检查结果</h1><div class="path">{html.escape(str(report_path))}</div><div id="message">点击问题即可在当前 CATPart 中定位；不会修改模型。</div>
<table><thead><tr><th>操作</th><th>状态</th><th>等级</th><th>问题编号</th><th>问题</th><th>涉及对象</th><th>测量值</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<script>async function locate(issue){{const b=[...document.querySelectorAll('button:not([data-fixed-disabled])')];b.forEach(x=>x.disabled=true);const m=document.getElementById('message');m.textContent='正在连接 CATIA 并定位 '+issue+'…';try{{const r=await fetch('/{token}/locate',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:new URLSearchParams({{issue_id:issue}})}});const d=await r.json();if(!r.ok)throw new Error(d.error||'定位失败');const items=d.selected_bodies?d.selected_bodies.map(x=>'Body #'+x.index):d.selected_components.map(x=>x.name);const count=d.selected_geometry_count||d.selected_count;m.textContent='已激活 CATIA 文档并选中 '+items.join('、')+'，共 '+count+' 个三维特征。请切换到 CATIA 查看高亮。';}}catch(e){{m.textContent='定位失败：'+e.message;}}finally{{b.forEach(x=>x.disabled=false);}}}}</script></body></html>'''
    return page.encode("utf-8")

def make_handler(report_path:Path,findings:list[dict],token:str):
    issue_ids={str(x["issue_id"]) for x in findings}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,_format,*_args): return
        def do_GET(self):
            if self.path.rstrip("/")!=f"/{token}": self.send_error(404); return
            body=render_page(report_path,findings,token); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            if self.path!=f"/{token}/locate": self.send_error(404); return
            length=min(int(self.headers.get("Content-Length","0")),4096); form=urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8")); issue_id=(form.get("issue_id") or [""])[0]
            try:
                if issue_id not in issue_ids: raise ValueError("报告中不存在该问题编号")
                connection=R18Connection(); connection.connect(); resolved=load_issue_target(report_path,issue_id); payload=select_issue_target(connection.active_document,resolved); status=200
            except Exception as exc: payload,status={"error":str(exc)},400
            body=json.dumps(payload,ensure_ascii=False).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    return Handler

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("report",nargs="?",type=Path); parser.add_argument("--no-browser",action="store_true"); args=parser.parse_args()
    report_path=args.report.resolve() if args.report else find_default_report(ROOT)
    if not report_path or not report_path.is_file(): raise SystemExit("未找到检查结果；请向Agent提供有效的 check.json 路径。")
    findings=actionable_findings(json.loads(report_path.read_text(encoding="utf-8"))); token=secrets.token_urlsafe(18); server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(report_path,findings,token)); url=f"http://127.0.0.1:{server.server_port}/{token}/"; print(url,flush=True)
    state_path=ROOT/"validation"/"result-viewer.json"; state_path.parent.mkdir(exist_ok=True); state_path.write_text(json.dumps({"status":"RUNNING","pid":os.getpid(),"url":url,"report":str(report_path)},ensure_ascii=False,indent=2),encoding="utf-8")
    def open_page():
        try:
            os.startfile(url)
        except Exception:
            webbrowser.open(url,new=1)
    if not args.no_browser: threading.Timer(0.3,open_page).start()
    server.serve_forever(); return 0
if __name__=="__main__": raise SystemExit(main())
