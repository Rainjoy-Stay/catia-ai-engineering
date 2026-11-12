"""Read-only source tracing from receipts, not a new live CATIA measurement."""
import json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve()
registry=json.loads((root/'registry.json').read_text(encoding='utf-8'))
mapping=json.loads((root/'body-mapping.json').read_text(encoding='utf-8'))
shape=registry['objects']['BATCH_0001::STEP_SOLID_0038'];candidates=[]
for record in mapping:
    if record.get('batch_id')!='BATCH_0001' or record.get('source_kind')!='BODY':continue
    if not record.get('volume_mm3') or not record.get('centroid_mm'):continue
    delta=math.dist(shape['centroid_mm'],record['centroid_mm'])
    volume_difference=abs(shape['volume_mm3']/record['volume_mm3']-1)
    candidates.append({'source_path':record.get('source_path'),'source_body_name':record['source_body_name'],
        'source_body_index':record['source_body_index'],'copied_label_match':record.get('batch_body_name')==shape['source_name'],
        'centroid_difference_mm':delta,'relative_volume_difference':volume_difference,
        'source_area_mm2':record.get('surface_area_mm2'),'occt_area_mm2':shape.get('surface_area_mm2'),
        'area_ratio':shape['surface_area_mm2']/record['surface_area_mm2'] if record.get('surface_area_mm2') else None,
        'source_volume_mm3':record['volume_mm3'],'occt_volume_mm3':shape['volume_mm3']})
candidates.sort(key=lambda x:(not x['copied_label_match'],x['relative_volume_difference'],x['centroid_difference_mm']))
atomic_json(root/'shape-review'/'b1s38-source-trace.json',{'shape_id':shape['shape_id'],
    'basis':'SAVED_EXPORT_RECEIPTS_NOT_LIVE_CATIA','receipt_sha256':digest(root/'body-mapping.json'),
    'candidates':candidates[:5],'mapping_verified':False,'conversion_failure_confirmed':False,
    'reason':'Name association plus volume/centroid is a trace candidate; large area discrepancy blocks equivalent-geometry claim',
    'catia_live_connection':'FAILED_COM_OPERATION_UNAVAILABLE','original_step_comparison':'NOT_PERFORMED'})
print(json.dumps(candidates[:2],ensure_ascii=False))
