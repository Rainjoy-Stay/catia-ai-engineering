"""Analyze all exact solid pairs in a named 10-20 object local STEP sample."""
import concurrent.futures
from collections import Counter
import json, math, subprocess, sys
from pathlib import Path

from tools.review_surface_recovery_pilot import digest


def box_gap(a,b):
    return math.sqrt(sum(max(0,a['min'][i]-b['max'][i],b['min'][i]-a['max'][i])**2 for i in range(3)))


def main():
    out=Path(sys.argv[1]).resolve(); scan=json.loads((out/'exterior_scan/batch_exterior_scan.json').read_text(encoding='utf-8'))
    mapping_path=out/'source_name_mapping.json'
    mapping=json.loads(mapping_path.read_text(encoding='utf-8'))['mapping']
    names={x['index']:x['final_stp_name'] for x in mapping if x['selected_for_report']}
    selected=[x for x in scan['records'] if x['source_body_index'] in names and x['source_body_index']!=832]
    solids=[x for x in selected if x.get('solid_count')==1 and x.get('records') and x['records'][0]['solid']['valid']]
    non_solid=[{'body_index':x['source_body_index'],'stp_name':names[x['source_body_index']],
                'status':'NOT_EVALUATED','reason':x.get('reason','NO_VALID_SINGLE_SOLID')}
               for x in selected if x not in solids]
    bounds=[x['records'][0]['solid']['bounds_mm'] for x in solids]
    adjacency=[(i,j) for i in range(len(solids)) for j in range(i+1,len(solids)) if box_gap(bounds[i],bounds[j])<=5]
    connected={0}
    while True:
        old=len(connected)
        for i,j in adjacency:
            if i in connected or j in connected: connected.update((i,j))
        if len(connected)==old: break
    if len(connected)!=len(solids): raise RuntimeError('Solid sample is not one spatial neighborhood')
    pairs=out/'pairs';pairs.mkdir(exist_ok=True);tasks=[];baseline=digest(out/'steps/export_audit.json')
    worker=Path(__file__).with_name('analyze_spatial_local_group.py')
    for i,a in enumerate(solids):
        for b in solids[i+1:]:
            stem=f"BODY_{a['source_body_index']}_{b['source_body_index']}";req=pairs/(stem+'.input.json');target=pairs/(stem+'.result.json')
            req.write_text(json.dumps({'bodies':[a,b],'baseline_sha256':baseline},ensure_ascii=False),encoding='utf-8');tasks.append((a,b,req,target))
    def run(task):
        a,b,req,target=task
        try:
            p=subprocess.run([sys.executable,str(worker),str(req),str(target)],capture_output=True,text=True,timeout=30)
            if p.returncode: raise RuntimeError(p.stderr[-500:])
            result=json.loads(target.read_text(encoding='utf-8'))
        except Exception as exc:
            result={'body_a':a['source_body_index'],'body_b':b['source_body_index'],'error':str(exc),
                    'decision':{'status':'NOT_EVALUATED','category':'UNDETERMINED','reason':'EXACT_PAIR_NOT_COMPLETED'}}
        result['name_a']=names[result['body_a']];result['name_b']=names[result['body_b']]
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(run,tasks))
    candidates=[]
    for item in selected:
        for record in item.get('records',[]):
            candidate=record['candidate']; finding=record.get('bend_radius_rule_finding')
            if candidate['geometry_kind']!='UNDETERMINED':
                candidates.append({'body_index':item['source_body_index'],'stp_name':names[item['source_body_index']],
                    'candidate':candidate,'bend_radius_rule_finding':finding})
    positive=[x for x in records if x.get('fact',{}).get('intersection_volume_mm3',0)>0]
    lo=[min(b['min'][i] for b in bounds) for i in range(3)];hi=[max(b['max'][i] for b in bounds) for i in range(3)]
    result={'schema_version':'named-local-demo.v1','scope':'20_SPATIALLY_CONNECTED_OBJECTS_19_EXACT_SOLIDS',
        'status':'NOT_EVALUATED','selected_object_count':len(selected),'exact_solid_count':len(solids),
        'non_solid_count':len(non_solid),'pair_count':len(records),'pair_errors':sum('error'in x for x in records),
        'bounds_mm':{'min':lo,'max':hi},'spatial_connectivity_verified':True,
        'decision_counts':dict(Counter(x['decision']['status'] for x in records)),
        'category_counts':dict(Counter(x['decision']['category'] for x in records)),
        'positive_volume_overlap_pairs':len(positive),'non_solid_objects':non_solid,
        'geometry_candidate_count':len(candidates),'geometry_candidates':candidates,'records':records,
        'name_mapping_file':str(mapping_path.resolve()),
        'renamed_step_file':str((out/'涡轮发动机_原名一致_20对象.stp').resolve()),
        'limitations':['STEP has no confirmed cavity','candidate exterior does not prove engineering pipe intent',
                       'HB 4-55-2002 nominal diameter table is not extrapolated outside 4-80 mm']}
    (out/'named_local_analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','geometry_candidates')},ensure_ascii=False))

if __name__=='__main__': main()
