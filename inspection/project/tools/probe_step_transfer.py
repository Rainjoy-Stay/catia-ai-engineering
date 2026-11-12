"""Read-only diagnostics of OCCT transfer associations."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from OCP.STEPControl import STEPControl_Reader
from OCP.StepShape import StepShape_ManifoldSolidBrep
from catia_checker.occt_brep import independent_geometry
reader=STEPControl_Reader();reader.ReadFile(sys.argv[1]);reader.TransferRoots()
model=reader.StepModel();tr=reader.WS().TransferReader();found=0
for i in range(1,model.NbEntities()+1):
    entity=model.Value(i);kind=entity.DynamicType().Name()
    if 'Brep' not in kind:continue
    print('ENTITY',i,type(entity).__name__,kind,isinstance(entity,StepShape_ManifoldSolidBrep),flush=True)
    shape=tr.ShapeResult(entity)
    print('RESULT',shape.IsNull(),flush=True)
    binder=tr.TransientProcess().Find(entity)
    print('BINDER',type(binder).__name__,binder.DynamicType().Name() if binder else None,flush=True)
    found+=1
    if found>=3:break
for _,shape in independent_geometry(reader.OneShape())[:3]:
    for mode in (0,1,2,3):
        entity=tr.EntityFromShapeResult(shape,mode)
        print('REVERSE',mode,type(entity).__name__,entity.DynamicType().Name() if entity else None,flush=True)
