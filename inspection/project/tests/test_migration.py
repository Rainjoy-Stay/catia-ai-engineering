import unittest
from types import SimpleNamespace
from unittest.mock import patch
from r18_connection import V5Connection
class MigrationTests(unittest.TestCase):
    def connect_release(self,value):
        conn=V5Connection()
        with patch('win32com.client.GetActiveObject',return_value=SimpleNamespace(SystemConfiguration=SimpleNamespace(Release=value))), patch('win32com.client.Dispatch') as launch:
            try:
                result=conn.connect()
                launch.assert_not_called()
                return result
            finally: conn.disconnect()
    def test_development_release_32(self):
        for value in ['V5R32','32','R32']:
            self.assertIn('DEV_V5_6R2022_RELEASE32',self.connect_release(value))
    def test_intranet_target_release_30(self):
        for value in ['V5R30','30','R30']:
            self.assertIn('INTRANET_TARGET_R30',self.connect_release(value))
    def test_other_v5_releases_use_compatible_mode(self):
        for value in ['V5R18','18','V5R19','118']:
            self.assertIn('CATIA_V5_GENERIC_COMPATIBILITY_MODE',self.connect_release(value))
    def test_unidentified_release_rejected(self):
        with self.assertRaises(RuntimeError): self.connect_release('unknown')
    def test_missing_release_rejected(self):
        with self.assertRaises(RuntimeError): self.connect_release(None)
    def test_mcp_modes(self):
        from start_mcp import make_server,ALLOWED
        with patch.dict('os.environ', {'CATIA_AGENT_MODE': 'full'}):
            server=make_server()
        self.assertIn('catia_scan_product_clashes',server._tool_router)
        self.assertIn('catia_add_component',server._tool_router)
        self.assertIn('catia_tubing_create_arrangement_run',server._tool_router)
        self.assertEqual(set(server._tool_router),ALLOWED)
        with patch.dict('os.environ', {'CATIA_AGENT_MODE': 'inspection'}):
            inspection_server=make_server()
        self.assertIn('catia_scan_product_clashes',inspection_server._tool_router)
        for name in ['catia_clear_main_body','catia_add_component','catia_close_document']:
            self.assertNotIn(name,inspection_server._tool_router)
        self.assertEqual(set(inspection_server._tool_router),ALLOWED)

    def test_custom_llm_provider(self):
        import catia_checker.llm_adapter as adapter
        with patch.dict(adapter._PROVIDER_FACTORIES,clear=True):
            adapter.register_llm_provider('company',lambda cfg: adapter.TemplateAdapter())
            response=adapter.create_llm_adapter({'llm':{'mode':'company'}}).explain({'document':'offline'})
            self.assertIn('offline',response.text)
            with self.assertRaises(ValueError): adapter.register_llm_provider('template',lambda cfg: None)
    def test_unified_mcp_without_llm(self):
        import json
        from unittest.mock import Mock
        from check_tool import CheckTool
        raw={'document':'SYNTHETIC_TEST.CATProduct','root_product':'test','method':'synthetic test only','clearance_mm':0.1,'conflicts':[],'truncated':False,'cleanup_verified':True,'source_saved_by_tool':False}
        module=Mock()
        module.execute.return_value=json.dumps(raw)
        with patch('pathlib.Path.write_text'), patch('pathlib.Path.mkdir'):
            tubing=Mock()
            tubing._arrangement_product.side_effect=RuntimeError('no native tubing')
            result=json.loads(CheckTool(module,tubing).execute('catia_check_assembly',{}))
        self.assertEqual(result['schema_version'],'1.1.0')
        self.assertIn('findings',result)
        module.execute.assert_called_once()
        with self.assertRaises(RuntimeError):
            module.execute.return_value='{"error":"no license"}'
            CheckTool(module,tubing).execute('catia_check_assembly',{})
