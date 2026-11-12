"""A source identity trace does not assert geometric equivalence."""
def trace_identity(identifier, objects, receipts):
    obj=objects[identifier];label=obj.get('source_name');batch=obj.get('batch_id')
    result={'shape_id':identifier,'source_identity_traced':False,'geometry_equivalence_verified':False}
    if not label or obj.get('identity_source')!='STEP_TRANSFER_ENTITY_SHAPE_ASSOCIATION':
        return {**result,'reason':'NO_REVERSE_TRANSFER_LABEL'}
    owners=[r for r in receipts if r.get('batch_id')==batch and r.get('batch_body_name')==label and r.get('source_kind')=='BODY']
    shapes=[o for o in objects.values() if o.get('batch_id')==batch and o.get('geometry_kind')=='SOLID' and o.get('source_name')==label]
    if len(owners)!=1 or len(shapes)!=1:return {**result,'reason':'AMBIGUOUS_SOURCE_OR_TRANSFER_LABEL'}
    receipt=owners[0]
    if receipt.get('mapping_method')!='UNIQUE_COPIED_NAME_AND_SPA_VOLUME_AREA' or receipt.get('target_original_name')!=receipt.get('source_body_name'):
        return {**result,'reason':'COPY_RECEIPT_NOT_VERIFIED'}
    return {**result,'source_identity_traced':True,'reason':'UNIQUE_COPY_RECEIPT_AND_REVERSE_TRANSFER_TRACE',
            'source_body_index':receipt['source_body_index'],'source_body_name':receipt['source_body_name'],
            'source_path':receipt['source_path'],'batch_id':batch,'copied_label':label,
            'limitations':['身份追踪不是完整形状等价证明','不修改几何匹配或原始判定']}
