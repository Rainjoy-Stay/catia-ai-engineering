"""Keep source differences distinct from confirmed conversion artifacts."""
def classify_source_comparison(original, cached_fact, cached_review):
    result={'classification':'UNRESOLVED','screen_pass':False,'conversion_confirmed':False,
            'excluded':False,'formal_verdict_modified':False}
    surface=cached_fact.get('surface') or {}
    details=cached_review.get('details') or {}
    if (surface.get('exact_brep') is True and surface.get('intersection_type')=='CONTACT'
        and surface.get('boundary_contact') is True and surface.get('surface_intersection') is False
        and not surface.get('penetration_confirmed') and not surface.get('crosses_surface_normal_sides')
        and details.get('input_valid')==[True,True] and details.get('common_valid') is True):
        result.update(classification='CONTACT_ALLOWED_BY_SCREEN_POLICY',screen_pass=True,
                      reason='有效缓存几何的精确结果为边界接触；按只查穿透规则通过，未证明转换伪干涉')
        return result
    original_details=original.get('details') or {}
    if original_details.get('input_valid')!=[True,True] or original_details.get('common_valid') is not True:
        result['reason']='原始对照未完成或几何无效';return result
    volume=original_details.get('common_volume_raw_mm3')
    if volume==0:
        result.update(classification='SOURCE_DIFFERENCE_CANDIDATE',reason='原始候选公共体积为零，批量为正；需来源认证和局部几何证据，未自动放行')
    elif isinstance(volume,(int,float)) and volume>0:
        result.update(classification='ORIGINAL_OVERLAP_OBSERVED',reason='原始候选也有正公共体积；不支持仅由批量转换制造，仍需微交集稳定性及局部穿越证据')
    else:result['reason']='原始公共体积不适用或无可用结果'
    return result
