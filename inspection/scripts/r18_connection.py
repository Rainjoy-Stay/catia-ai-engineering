"""Attach to CATIA V5 and classify the validated development or target release."""
import re
from catia_mcp.connection import CATIAConnection
class V5Connection(CATIAConnection):
    def connect(self):
        import pythoncom
        import win32com.client
        if not self._initialized_com:
            pythoncom.CoInitialize()
            self._initialized_com = True
        app = win32com.client.GetActiveObject('CATIA.Application')
        try:
            release = str(app.SystemConfiguration.Release).strip()
        except Exception as exc:
            self.app = None
            raise RuntimeError('Cannot read CATIA release. Verify CATIA COM registration and SystemConfiguration.Release.') from exc
        match = re.fullmatch(r'(?:CATIA\s*)?(?:V5)?R?(\d+)(?:\.0)?', release, re.I)
        if not match:
            self.app = None
            raise RuntimeError('Cannot identify a CATIA V5 release: ' + release)
        self.app = app
        number = int(match.group(1))
        if number == 32:
            compatibility = 'DEV_V5_6R2022_RELEASE32'
        elif number == 30:
            compatibility = 'INTRANET_TARGET_R30'
        else:
            compatibility = 'CATIA_V5_GENERIC_COMPATIBILITY_MODE'
        return f'Connected to CATIA V5; release={release}; mode={compatibility}'

# Compatibility alias for existing imports and deployed Harness configurations.
R18Connection = V5Connection
