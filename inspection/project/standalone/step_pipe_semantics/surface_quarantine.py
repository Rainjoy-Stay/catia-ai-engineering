"""Quarantine only exact cached geometry and diagnosed face identities."""

def matches_quarantine(face_id,brep_sha256,entries):
    return any(e.get('face_id')==face_id and e.get('input_brep_sha256')==brep_sha256
               and e.get('stage')=='OCCT_CONVERT_TO_ANALYTICAL'
               and e.get('exit_code')==3221225477 for e in entries)
