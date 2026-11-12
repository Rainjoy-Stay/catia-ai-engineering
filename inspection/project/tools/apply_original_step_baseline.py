"""Persist the authorized baseline and one evidence-gated screening overlay."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import digest,atomic_json
root=Path(sys.argv[1]).resolve()
subprocess.run([sys.executable,str(Path(__file__).with_name('verify_ten_certificates.py')),str(root)],check=True)
review=root/'shape-review'
choice=json.loads((review/'baseline-choice.json').read_text(encoding='utf-8'))
certificate=json.loads((review/'ten-evidence-certificates.json').read_text(encoding='utf-8'))
if choice.get('baseline')!='ORIGINAL_STEP' or choice.get('authorization')!='USER_EXPLICIT':
    raise ValueError('Explicit original STEP baseline required')
for key in ('geometry_fingerprint','source_step_sha256'):
    if choice[key]!=certificate[key]:raise ValueError('Baseline binding mismatch')
row=certificate['rows'][3]
if row['classification']!='LOCAL_CONVERSION_PATH_DIFFERENCE_WITNESSED':raise ValueError('No difference evidence')
original=json.loads((review/'original-pair-03.json').read_text(encoding='utf-8'))
if original.get('input_valid')!=[True,True] or original.get('common_valid') is not True or original.get('common_solid_count')!=0:
    raise ValueError('Original pair geometry gate failed')
provenance=json.loads((review/'ten-provenance-audit.json').read_text(encoding='utf-8'))['rows']
if any(sum(r['shape_id']==identifier and r.get('source_identity_traced') is True for r in provenance)!=1 for identifier in row['pair']):
    raise ValueError('Unique source trace required')
local=row['local_review']
if local.get('cached_internal_witness_count')!=6 or local.get('original_internal_witness_count')!=0 or local.get('missing_witness_regions')!=0:
    raise ValueError('Local witness gate failed')
result={'baseline':choice['baseline'],'geometry_fingerprint':certificate['geometry_fingerprint'],
    'source_step_sha256':certificate['source_step_sha256'],
    'certificate_sha256':digest(review/'ten-evidence-certificates.json'),
    'baseline_choice_sha256':digest(review/'baseline-choice.json'),
    'rows':[{'pair':row['pair'],'screen_pass':True,'classification':'ORIGINAL_STEP_CONVERSION_OVERLAP_EXCLUDED',
        'reason':'用户确认原始STEP基准；来源追踪唯一、原始双方及求交有效且无公共实体；排除转换路径新增重叠',
        'formal_verdict_modified':False}],
    'other_pairs_modified':False,'source_modified':False,
    'limitations':['采用已记录的声明顺序与复制回执来源追踪，不是原生设计身份认证',
        '仅排除此对象对的转换新增实体重叠，不宣称设计合规或其他最小间隙达标']}
atomic_json(review/'original-step-screening-overlay.json',result)
print(json.dumps(result,ensure_ascii=False))
