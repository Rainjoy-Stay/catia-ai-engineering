import unittest
from standalone.step_pipe_semantics.surface_quarantine import matches_quarantine

class QuarantineIdentityAcceptance(unittest.TestCase):
    def test_exact_geometry_only(self):
        entry={'face_id':'SOLID::FACE_1','input_brep_sha256':'original',
               'stage':'OCCT_CONVERT_TO_ANALYTICAL','exit_code':3221225477}
        self.assertTrue(matches_quarantine('SOLID::FACE_1','original',[entry]))
        self.assertFalse(matches_quarantine('SOLID::FACE_1','changed',[entry]))
        self.assertFalse(matches_quarantine('OTHER::FACE_1','original',[entry]))
        self.assertFalse(matches_quarantine('SOLID::FACE_1','original',[{**entry,'exit_code':0}]))

if __name__=='__main__': unittest.main()
