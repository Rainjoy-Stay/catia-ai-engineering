"""Human labels and native localization evidence, separate from inspection facts."""
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

LOCK = threading.RLock()

def paths(directory):
    config = json.loads((Path(directory)/'human-review-config.json').read_text(encoding='utf-8'))
    allowed = Path(__file__).resolve().parents[3]/'output'
    annotation = Path(config['annotation_path']).resolve()
    evidence = Path(config['evidence_root']).resolve()
    if not annotation.is_relative_to(allowed) or not evidence.is_relative_to(allowed):
        raise ValueError('Human review paths outside workspace output')
    return annotation, evidence

def read_round(directory):
    annotation, _ = paths(directory)
    with LOCK:
        return json.loads(annotation.read_text(encoding='utf-8'))

def image_path(directory, case_id, image_id):
    _, root = paths(directory)
    case = next((x for x in read_round(directory)['cases'] if x['case_id']==case_id), None)
    entry = next((x for x in (case or {}).get('ui', {}).get('images', []) if x['id']==image_id), None)
    if entry is None:
        raise ValueError('Unknown evidence image')
    path = (root/entry['relative_path']).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
        raise ValueError('Evidence image changed')
    return path

def update_label_file(path, options):
    """Atomic audited update; immutable evidence and formal verdicts are untouched."""
    label = options.get('label')
    reason = options.get('reason', '')
    if label not in ('PASS', 'FAIL', 'REVIEW', None) or not isinstance(reason, str) or len(reason)>2000:
        raise ValueError('Invalid human label or reason')
    with LOCK:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        case = next((x for x in value['cases'] if x['case_id']==options.get('case_id')), None)
        if case is None:
            raise ValueError('Unknown case')
        if options.get('evidence_fingerprint')!=case['evidence_fingerprint'] or options.get('revision')!=case.get('label_revision', 0):
            raise ValueError('Evidence or label changed; reload before saving')
        now = datetime.now(timezone.utc).isoformat()
        case.setdefault('label_history', []).append({'time':now, 'old_label':case.get('human_label'), 'old_reason':case.get('human_reason'), 'new_label':label, 'new_reason':reason, 'evidence_fingerprint':case['evidence_fingerprint'], 'origin':'HUMAN_UI_SUBMISSION'})
        case.update(human_label=label, human_reason=reason, label_revision=case.get('label_revision',0)+1,
                    labelled_at=now, state='LABELLED' if label else 'AWAITING_USER_LABEL')
        temporary = Path(path).with_suffix('.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temporary,path)
        return {'ok':True,'case':case,'training_performed':False,'rules_promoted':False}

def save_label(directory, options):
    path, _ = paths(directory)
    return update_label_file(path, options)
