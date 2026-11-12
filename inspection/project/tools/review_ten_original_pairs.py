"""Bounded native original STEP comparison for all seven solid review pairs."""
import json,re,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import atomic_json,digest
root=Path(sys.argv[1]).resolve();tools=Path(__file__).resolve().parent
review=json.loads((root/'shape-review/ten-pair-source-review.json').read_text(encoding='utf-8'))
audit=json.loads((root/'shape-review/ten-pair-mapping-audit.json').read_text(encoding='utf-8'))
registry=json.loads((root/'registry.json').read_text(encoding='utf-8'))['objects']
candidates={r['shape_id']:r['candidates'][0] for r in audit['rows'] if r.get('candidates')}
rows=[]
for index,row in enumerate(review['rows']):
    result={'pair':row['pair'],'conversion_confirmed':False,'excluded':False,'source_association_certified':False}
    if any(registry[i]['geometry_kind']!='SOLID' for i in row['pair']):
        result.update(status='SURFACE_ELEMENT_MAPPING_REQUIRED',reason='原始源面元素对应尚未建立，不能认定转换重复')
    else:
        labels=[]
        try:
            for identifier in row['pair']:
                candidate=candidates[identifier]
                label=int(re.search(r'#(\d+)$',candidate['source_body_name']).group(1));labels.append(label)
                directory=root/f'shape-review/original-{label}'
                if not (directory/'audit.json').exists():
                    subprocess.run([sys.executable,str(tools/'check_original_3067.py'),str(root),str(label)],
                                   timeout=60,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                source=json.loads((directory/'audit.json').read_text(encoding='utf-8'))
                if source.get('actual_target_label',source.get('step_entity'))!=label:raise ValueError('Original target label receipt mismatch')
            path=root/f'shape-review/original-pair-{index:02d}.json'
            subprocess.run([sys.executable,str(tools/'review_shape_candidates.py'),str(root),'--worker',
                            *[str(root/f'shape-review/original-{label}/target.brep') for label in labels],str(path)],
                           timeout=20,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            details=json.loads(path.read_text(encoding='utf-8'))
            result.update(status='ORIGINAL_PAIR_RECOMPUTED',original_labels=labels,details=details,
                          result_sha256=digest(path),reason='声明顺序与来源候选追踪；尚需完整几何映射认证，不自动放行')
        except subprocess.TimeoutExpired:result.update(status='ORIGINAL_REVIEW_TIMEOUT',reason='独立原始复核达到时间上限')
        except Exception as exc:result.update(status='ORIGINAL_REVIEW_ERROR',reason=str(exc))
    rows.append(result);atomic_json(root/'shape-review/ten-original-pairs.json',{'rows':rows,'source_modified':False,'automatic_exclusions':0})
    print(json.dumps({'index':index,'pair':row['pair'],'status':result['status'],
                      'volume':result.get('details',{}).get('common_volume_raw_mm3'),'reason':result['reason']},ensure_ascii=False),flush=True)
