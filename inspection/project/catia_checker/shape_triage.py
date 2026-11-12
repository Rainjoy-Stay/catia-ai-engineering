"""Read-only morphology hypotheses. Never exempts or rewrites exact facts."""
import math

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def classify(a,b,fact):
    result={'category':'UNRESOLVED','label':'证据不足','excluded':False,
            'conversion_confirmed':False,'evidence':{},'next_action':'核验来源对应和局部 BREP；不得自动排除'}
    common=fact.get('common') or {};surface=fact.get('surface') or {};distance=fact.get('distance') or {}
    volume=common.get('intersection_volume_mm3')
    if common.get('exact_brep') and number(volume) and volume>0:
        result['evidence']['common_volume_mm3']=volume
        volumes=[a.get('volume_mm3'),b.get('volume_mm3')]
        if all(number(v) and v>0 for v in volumes):
            ratios=[volume/v for v in volumes];result['evidence']['overlap_fractions']=ratios
            bounds=[x.get('bounds_mm') or {} for x in (a,b)]
            try:
                delta=max(abs(bounds[0][side][i]-bounds[1][side][i]) for side in ('min','max') for i in range(3))
            except (KeyError,IndexError,TypeError):delta=None
            result['evidence']['bounds_max_delta_mm']=delta
            # High common fractions plus matching bounds suggest coincident solids,
            # but cannot distinguish duplication from a misplaced assembly instance.
            if all(.999<=r<=1.001 for r in ratios) and delta is not None and delta<=.001:
                result.update(category='COINCIDENT_SOLID_CANDIDATE',label='疑似重合实体／重复表示',
                    next_action='核对是否同一来源重复导出，或两个独立对象放置重合')
                return result
            if max(ratios)<=.001:
                result.update(category='SMALL_OVERLAP_CANDIDATE',label='小比例重叠，原因待核实',
                    next_action='检查交集形状及来源差异；小体积不能证明薄片或转换异常')
                return result
        result.update(category='SOLID_OVERLAP',label='已测得实体重叠，工程原因待确认',
                      next_action='核验来源几何与配合意图；不能仅凭体积认定不允许的真实干涉')
        return result
    if surface.get('exact_brep'):
        flags={k:surface.get(k) for k in ('coincident_surface_overlap','continuous_surface_contact',
            'boundary_contact','surface_intersection','penetration_evidence_available','penetration_confirmed')}
        result['evidence']['surface']=flags
        if surface.get('penetration_evidence_available') and (surface.get('penetration_confirmed') or surface.get('crosses_surface_normal_sides')):
            result.update(category='SURFACE_CROSSING',label='有曲面穿越证据，来源待复核')
        elif surface.get('coincident_surface_overlap'):
            result.update(category='COINCIDENT_SURFACE_CANDIDATE',label='疑似重合面／附属面表示',
                next_action='检查完整面域和来源归属；局部重合不能证明整面重复')
        elif surface.get('continuous_surface_contact') or surface.get('boundary_contact'):
            result.update(category='CONTACT',label='接触／连续贴合线索，不是转换异常证据')
        elif surface.get('surface_intersection'):
            result.update(category='SECTION_UNRESOLVED',label='只有截交线，穿透与用途待核实')
        else:
            gap=distance.get('minimum_distance_mm')
            if distance.get('exact_brep') and number(gap) and gap>0:
                result.update(category='SEPARATED',label='精确距离证明分离')
    elif common.get('exact_brep') and number(volume) and volume==0:
        result.update(category='NO_SOLID_OVERLAP',label='未测得实体公共体积')
    return result
