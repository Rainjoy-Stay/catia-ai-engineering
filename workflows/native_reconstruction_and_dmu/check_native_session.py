import sys,json
from pathlib import Path
r=Path.cwd();sys.path.insert(0,str(r/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection
c=CATIAConnection();c.connect();a=c.app
print('documents',a.Documents.Count,flush=True)
for k in range(1,a.Documents.Count+1):
 d=a.Documents.Item(k)
 if str(d.Name).endswith('.CATProduct'):print(d.Name,flush=True)
try:print('active',a.ActiveDocument.Name,'zoom',a.ActiveWindow.ActiveViewer.Viewpoint3D.Zoom,flush=True)
except Exception as e:print(type(e).__name__,str(e),flush=True)
