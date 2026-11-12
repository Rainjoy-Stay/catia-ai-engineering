"""Associate STEP labels with transferred topology, never text or traversal order."""
from OCP.StepShape import StepShape_ManifoldSolidBrep, StepShape_OpenShell, StepShape_ClosedShell


def transferred_shape_names(reader, items):
    transfer=reader.WS().TransferReader(); model=reader.StepModel(); result=[]
    for _,shape in items:
        # Mode 1 consults the last transfer process. TransferRoots does not
        # populate the final-record mode 0 used by ShapeResult(entity).
        origin=transfer.EntityFromShapeResult(shape,1)
        name=None; evidence=[]
        if origin is not None and isinstance(origin,(StepShape_ManifoldSolidBrep,StepShape_OpenShell,StepShape_ClosedShell)):
            label=origin.Name()
            if label is not None and label.ToCString().strip():
                name=label.ToCString().strip()
                evidence=[{'entity_number':model.Number(origin),
                           'entity_type':origin.DynamicType().Name(),
                           'name':name,'reverse_transfer_mode':1}]
        result.append({'name':name,
                       'association':'STEP_TRANSFER_ENTITY_SHAPE_ASSOCIATION' if name else None,
                       'conflicting_labels':[],'entities':evidence})
    return result
