import pythoncom
p=r'D:\Program Files\Dassault Systemes\B32\win_b64\code\bin\InfTypeLib.tlb'
lib=pythoncom.LoadTypeLib(p)
for i in range(lib.GetTypeInfoCount()):
 name=lib.GetDocumentation(i)[0]
 if name not in ('CatVisPropertyType','CatWindowState','CatScriptLanguage','CatRenderingMode'):continue
 ti=lib.GetTypeInfo(i);attr=ti.GetTypeAttr()
 print(name,attr,flush=True)
 for k in range(30):
  try:
   v=ti.GetVarDesc(k);print(ti.GetDocumentation(v[0])[0],v,flush=True)
  except pythoncom.com_error:break
