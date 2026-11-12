"""Build an auditable pilot from completed exact facts, without changing the run."""
import argparse,json,sys,hashlib
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.shape_triage import classify
from catia_checker.occt_session_cache import atomic_json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
    root=args.directory.resolve();raw=(root/'checkpoint.json').read_bytes();saved=json.loads(raw)
    registry_raw=(root/'registry.json').read_bytes();objects=json.loads(registry_raw)['objects'];rows=[]
    counts=Counter()
    for item in saved['completed_pairs']:
        pair=item['pair'];triage=classify(objects.get(pair[0],{}),objects.get(pair[1],{}),item['fact'])
        counts[triage['category']]+=1
        if triage['category'] not in ('SEPARATED','NO_SOLID_OVERLAP','CONTACT'):
            rows.append({'pair':pair,'names':[objects.get(i,{}).get('source_body_name') or objects.get(i,{}).get('source_path') or objects.get(i,{}).get('source_name') for i in pair],**triage})
    output={'schema_version':'shape-triage-pilot.v1','basis':'COMPLETED_EXACT_FACTS_AND_DESCRIPTORS',
            'checkpoint_sha256':hashlib.sha256(raw).hexdigest(),'registry_sha256':hashlib.sha256(registry_raw).hexdigest(),
            'geometry_fingerprint':saved['geometry_fingerprint'],'reviewed_pairs':len(saved['completed_pairs']),
            'uncomputed_pairs_included':False,'automatic_exclusions':0,'counts':dict(counts),'rows':rows,
            'limitations':['仅规则化形状预归因，不是 AI 最终工程判断','未计算交集薄片厚度，未核验完整边界一致性','尚未进行原始 STEP／CATIA 来源对照','不改变原始结果和检查点']}
    atomic_json(root/'shape-triage-pilot.json',output);print(json.dumps({'reviewed_pairs':output['reviewed_pairs'],'counts':dict(counts),'automatic_exclusions':0},ensure_ascii=False))
if __name__=='__main__':main()
