"""Candidate geometry outside a defect region does not validate an invalid solid."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve();review=root/'shape-review'
local=json.loads((review/'original-major-defect-localization.json').read_text(encoding='utf-8'))
triage=json.loads((review/'original-retry-triage.json').read_text(encoding='utf-8'))
defects={r['label']:r for r in local['rows']};rows=[]
def separated(a,b):
    return any(a['min'][i]>b['max'][i] or b['min'][i]>a['max'][i] for i in range(3))
for item in triage['rows']:
    if item['category']!='INVALID_ORIGINAL_TRANSFER_INPUT':continue
    for side,label in enumerate(item['original_labels']):
        if label not in defects:continue
        other=item['original_labels'][1-side]
        audit=json.loads((review/f'original-{other}/audit.json').read_text(encoding='utf-8'))
        hits=[r['traversal_index'] for r in defects[label]['defects'] if r['kind']=='FACE'
            and not separated(r['bounds_mm'],audit['record']['bounds_mm'])]
        rows.append({'pair':item['pair'],'defective_label':label,'other_label':other,
            'candidate_defect_face_indices':hits,'partner_bounds_outside_all_defect_faces':not hits,
            'screen_pass':False,'reason':'远离已定位问题面，不证明整个无效实体的内部/空腔分类可靠'})
source=Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')
text=source.read_text(encoding='ascii',errors='replace')
records={label:re.search(r'^\s*#'+str(label)+r'\s*=\s*(.*?);',text,re.M|re.S).group(1) for label in defects}
result={'rows':rows,'outside_defect_region_count':sum(r['partner_bounds_outside_all_defect_faces'] for r in rows),
    'source_records':records,'source_step_sha256':digest(source),'source_modified':False,
    'automatic_passes':0,'limitation':'Valid transferred subsolids are not assumed to be material; BREP_WITH_VOIDS ownership must be resolved'}
atomic_json(review/'original-defect-pair-regions.json',result)
print(json.dumps({'evaluated_major_defect_sides':len(rows),'outside_defect_region_count':result['outside_defect_region_count'],
    'source_records':records},ensure_ascii=True))
