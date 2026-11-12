import ast,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_resume_fast as n
tree=ast.parse((Path(__file__).resolve().parent/'native_resume_exact.py').read_text(encoding='utf8'))
helpers=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='helpers' for t in node.targets))
F=n.F;data=json.loads((F/'resume-exact-solids.json').read_text(encoding='utf8'))
reg={r['id']:r for r in json.loads((F/'preparation-audit.json').read_text(encoding='utf8'))['records']}
index={r['id']:r['index'] for r in json.loads((F/'fast-display-before.json').read_text(encoding='utf8'))['items']}
try:
 for i,old in enumerate(data['rows']):
  if old['status']!='NEEDS_REVIEW':continue
  a,b=reversed(old['pair']);code=f'Function Run()\nRun=CheckPair({index[a]},{index[b]},"{old["issue_id"]}")\nEnd Function'
  new=json.loads(n.evaluate(helpers+code));new['original_attempt']=old;new['operator_order']='REVERSED'
  new['status']='CONFIRMED_SOLID_OVERLAP' if new['error_number']==0 and new['volume_mm3']>1e-6 else 'NEEDS_REVIEW'
  if new['error_number']==0 and new['volume_mm3']>min(reg[k]['volume_mm3'] for k in new['pair'])+1e-5:raise RuntimeError('Common volume exceeds input')
  data['rows'][i]=new;n.save('resume-exact-solids.json',data);print(json.dumps(new,ensure_ascii=False),flush=True)
finally:
 n.app.Documents.Item(n.DOC).Activate();n.app.RefreshDisplay=True;n.app.HSOSynchronized=True
