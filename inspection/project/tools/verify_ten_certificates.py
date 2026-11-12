"""Verify all recorded bytes and model binding before consuming a certificate."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catia_checker.occt_session_cache import digest,atomic_json
root=Path(sys.argv[1]).resolve()
certificate=json.loads((root/'shape-review/ten-evidence-certificates.json').read_text(encoding='utf-8'))
checkpoint=json.loads((root/'checkpoint.json').read_text(encoding='utf-8'))
errors=[]
if certificate['geometry_fingerprint']!=checkpoint['geometry_fingerprint']:errors.append('MODEL_FINGERPRINT_CHANGED')
for name,expected in certificate['evidence_sha256'].items():
    path=(root/name).resolve()
    if not path.is_relative_to(root):raise ValueError('Evidence path escapes run directory')
    if not path.is_file() or digest(path)!=expected:errors.append('EVIDENCE_CHANGED:'+name)
source=Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp')
if digest(source)!=certificate['source_step_sha256']:errors.append('SOURCE_STEP_CHANGED')
if len(certificate['rows'])!=10:errors.append('INCOMPLETE_TEN_PAIR_SCOPE')
summary=json.loads((root/'shape-review/ten-comparison-summary.json').read_text(encoding='utf-8'))
actual_pairs=[tuple(r['pair']) for r in certificate['rows']]
expected_pairs=[tuple(r['pair']) for r in summary['rows']]
if actual_pairs!=expected_pairs or len(set(actual_pairs))!=10:errors.append('TEN_PAIR_IDENTITY_MISMATCH')
if certificate.get('source_modified') is not False:errors.append('SOURCE_MODIFICATION_NOT_EXCLUDED')
if certificate.get('automatic_conversion_exclusions')!=0:errors.append('AUTOMATIC_EXCLUSION_NOT_ALLOWED')
if any(r.get('formal_verdict_modified') is not False for r in certificate['rows']):errors.append('FORMAL_VERDICT_MODIFIED')
if any(r['conversion_confirmed'] for r in certificate['rows']):errors.append('UNAUTHORIZED_CONVERSION_EXCLUSION')
if any(r['screen_pass'] and r['classification']!='CONTACT_ALLOWED_BY_SCREEN_POLICY' for r in certificate['rows']):errors.append('UNSUPPORTED_PASS')
result={'evidence_integrity_verified':not errors,'errors':errors,'evidence_files_checked':len(certificate['evidence_sha256']),
        'scope_pairs':len(certificate['rows']),'formal_engineering_acceptance':False,
        'certificate_sha256':digest(root/'shape-review/ten-evidence-certificates.json')}
atomic_json(root/'shape-review/ten-certificate-verification.json',result);print(json.dumps(result,ensure_ascii=False))
if errors:raise SystemExit(1)
