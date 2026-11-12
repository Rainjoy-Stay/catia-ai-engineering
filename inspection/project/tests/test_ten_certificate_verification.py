import contextlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from catia_checker.occt_session_cache import digest


class CertificateVerificationTests(unittest.TestCase):
    def verify(self, mutate=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / 'shape-review'
            review.mkdir()
            pairs = [[f'A{i}', f'B{i}'] for i in range(10)]
            summary = review / 'ten-comparison-summary.json'
            summary.write_text(json.dumps({'rows': [{'pair': p} for p in pairs]}))
            (root / 'checkpoint.json').write_text(json.dumps({'geometry_fingerprint': 'MODEL'}))
            evidence = root / 'evidence.json'
            evidence.write_text('{}')
            certificate = {
                'geometry_fingerprint': 'MODEL', 'source_step_sha256': 'SOURCE',
                'evidence_sha256': {'evidence.json': digest(evidence),
                    'shape-review/ten-comparison-summary.json': digest(summary)},
                'source_modified': False, 'automatic_conversion_exclusions': 0,
                'rows': [{'pair': p, 'conversion_confirmed': False,
                    'formal_verdict_modified': False, 'screen_pass': False,
                    'classification': 'ORIGINAL_LOCAL_OVERLAP_WITNESSED'} for p in pairs],
            }
            if mutate:
                mutate(certificate, root)
            (review / 'ten-evidence-certificates.json').write_text(json.dumps(certificate))
            def fixture_digest(path):
                if str(path).replace('\\', '/').startswith('F:/'):
                    return 'SOURCE'
                return digest(path)
            script = Path(__file__).resolve().parents[1] / 'tools/verify_ten_certificates.py'
            with patch('sys.argv', [str(script), str(root)]), patch(
                'catia_checker.occt_session_cache.digest', side_effect=fixture_digest
            ), contextlib.redirect_stdout(io.StringIO()):
                try:
                    runpy.run_path(str(script), run_name='__main__')
                except SystemExit as exc:
                    self.assertEqual(exc.code, 1)
            return json.loads((review / 'ten-certificate-verification.json').read_text())

    def test_untouched_fixture_passes(self):
        self.assertTrue(self.verify()['evidence_integrity_verified'])

    def test_changed_evidence_rejected(self):
        result = self.verify(lambda c, r: (r / 'evidence.json').write_text('{"changed":true}'))
        self.assertIn('EVIDENCE_CHANGED:evidence.json', result['errors'])

    def test_duplicate_pair_rejected(self):
        result = self.verify(lambda c, r: c['rows'][1].update(pair=c['rows'][0]['pair']))
        self.assertIn('TEN_PAIR_IDENTITY_MISMATCH', result['errors'])

    def test_wrong_model_rejected(self):
        result = self.verify(lambda c, r: c.update(geometry_fingerprint='OTHER'))
        self.assertIn('MODEL_FINGERPRINT_CHANGED', result['errors'])

    def test_unsupported_pass_rejected(self):
        result = self.verify(lambda c, r: c['rows'][3].update(screen_pass=True))
        self.assertIn('UNSUPPORTED_PASS', result['errors'])

    def test_conversion_exclusion_rejected(self):
        result = self.verify(lambda c, r: c['rows'][3].update(conversion_confirmed=True))
        self.assertIn('UNAUTHORIZED_CONVERSION_EXCLUSION', result['errors'])

    def test_formal_verdict_change_rejected(self):
        result = self.verify(lambda c, r: c['rows'][3].update(formal_verdict_modified=True))
        self.assertIn('FORMAL_VERDICT_MODIFIED', result['errors'])
