"""Measured convergence gates; reported integration error alone is insufficient."""
import math
def assess_integrations(samples, volume_limit=1e-5, centroid_limit_mm=1e-4):
    if len(samples)<2:return {'stable':False,'reason':'INSUFFICIENT_SAMPLES'}
    a,b=samples[-2:]
    values=[a['volume_mm3'],b['volume_mm3'],*a['centroid_mm'],*b['centroid_mm']]
    if not all(math.isfinite(v) for v in values):return {'stable':False,'reason':'NONFINITE_RESULT'}
    volume_delta=abs(a['volume_mm3']-b['volume_mm3'])/max(abs(a['volume_mm3']),abs(b['volume_mm3']),1e-12)
    centroid_delta=math.dist(a['centroid_mm'],b['centroid_mm'])
    return {'stable':volume_delta<=volume_limit and centroid_delta<=centroid_limit_mm,
            'relative_volume_change':volume_delta,'centroid_change_mm':centroid_delta,
            'volume_limit':volume_limit,'centroid_limit_mm':centroid_limit_mm,
            'reason':'NUMERICAL_CONVERGENCE_ONLY_NOT_GEOMETRY_EQUIVALENCE'}
