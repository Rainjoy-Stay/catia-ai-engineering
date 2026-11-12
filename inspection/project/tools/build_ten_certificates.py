"""Model-bound evidence certificates, not automatic engineering acceptance."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve()
summary=json.loads((root/'shape-review/ten-comparison-summary.json').read_text(encoding='utf-8'))
local=json.loads((root/'shape-review/ten-local-review.json').read_text(encoding='utf-8'))
point_lookup={r['pair_index']:r for r in local['rows']}
evidence_paths=['checkpoint.json','registry.json','body-mapping.json','shape-review/ten-provenance-audit.json',
    'shape-review/ten-comparison-summary.json','shape-review/ten-local-review.json']
evidence_paths.extend('shape-review/'+name for name in (
    'contact-shell-source-scope.json','contact-original-face-candidates.json',
    'live-contact-shell-inventory.json','native-contact-candidate-distances.json',
    'native-surface-330.json','native-surface-331.json','native-surface-332.json',
    'contact-adaptive-surface-integration.json','original-3068/audit.json','original-3068/target.brep'))
evidence_paths.extend(f'shape-review/local-penetration-pair-{i:02d}.json' for i in range(3,10))
evidence_paths.extend(f'shape-review/original-pair-{i:02d}.json' for i in range(3,10))
original_pairs=json.loads((root/'shape-review/ten-original-pairs.json').read_text(encoding='utf-8'))['rows']
for label in sorted({label for row in original_pairs for label in row.get('original_labels',[])}):
    evidence_paths.extend([f'shape-review/original-{label}/target.brep',f'shape-review/original-{label}/audit.json'])
for identifier in sorted({identifier for row in original_pairs if row.get('original_labels') for identifier in row['pair']}):
    paths=list((root/'occt-cache/pairs').rglob(identifier.replace('::','_')+'.brep'))
    if len(paths)!=1:raise ValueError('Ambiguous BREP input')
    if digest(paths[0])!=paths[0].with_suffix('.sha256').read_text().strip():raise ValueError('BREP cache hash mismatch')
    evidence_paths.append(paths[0].relative_to(root).as_posix())
evidence={p:digest(root/p) for p in evidence_paths}
rows=[]
for index,entry in enumerate(summary['rows']):
    row={'pair':entry['pair'],'classification':entry['classification'],'screen_pass':entry['screen_pass'],
         'conversion_confirmed':False,'formal_verdict_modified':False,'reason':entry['reason']}
    if index>=3:
        point=point_lookup.get(index,{})
        row['local_review']=point
        if point.get('original_internal_witness_count',0)>0:
            row.update(classification='ORIGINAL_LOCAL_OVERLAP_WITNESSED',screen_pass=False,
                       reason='原始候选双方内部已有见证点；几何局部重叠成立，但设计是否允许尚未判断')
        elif index==3 and point.get('cached_internal_witness_count')==6 and point.get('missing_witness_regions')==0:
            original=json.loads((root/'shape-review/original-pair-03.json').read_text(encoding='utf-8'))
            if original.get('common_solid_count')==0 and original.get('input_valid')==[True,True] and original.get('common_valid') is True:
                row.update(classification='LOCAL_CONVERSION_PATH_DIFFERENCE_WITNESSED',screen_pass=False,
                    reason='原始候选无公共实体；缓存两处交集共6个内部点在原始第二实体外部。局部路径差异已证实；整对排除仍需明确原始STEP基准')
    rows.append(row)
certificate={'schema_version':'ten-pair-evidence-certificates.v1','geometry_fingerprint':summary['geometry_fingerprint'],
             'source_step_sha256':digest(Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')),
             'evidence_sha256':evidence,'rows':rows,'counts':dict(Counter(r['classification'] for r in rows)),
             'source_modified':False,'automatic_conversion_exclusions':0,
             'limitations':['原始STEP声明顺序和复制回执追踪，不是CATIA原生设计身份认证',
                            '点采样没有完整覆盖边界，但严格内部见证可证实局部重叠','不推断配合意图或工程允许量']}
atomic_json(root/'shape-review/ten-evidence-certificates.json',certificate)
print(json.dumps({'counts':certificate['counts'],'certificate_sha256':digest(root/'shape-review/ten-evidence-certificates.json')},ensure_ascii=False))
