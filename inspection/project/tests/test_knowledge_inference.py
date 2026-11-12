import unittest
from catia_checker.model_understanding.knowledge_inference import compile_knowledge_base,infer_object,propagate_over_graph
CONFIG={"systems":{"FUEL":{"aliases":["燃油"],"line_prefixes":["FUEL"],"equipment_keywords":["燃油泵","喷嘴"],"port_keywords":[],"specification_keywords":[]},"HYDRAULIC":{"aliases":["液压"],"line_prefixes":["HYD"],"equipment_keywords":["液压泵","作动筒"],"port_keywords":[],"specification_keywords":[]}}}
class Tests(unittest.TestCase):
 def test_case(self):
  c={"object_id":"A","features":{"part_number":"PN-1"},"labels":{"object_type":"PIPE","system_type":"FUEL"},"label_source":"APPROVED"}
  r=infer_object(compile_knowledge_base(CONFIG,[c]),{"object_id":"B","features":{"part_number":"PN-1"}}); self.assertEqual(r["system_type"]["label"],"FUEL")
 def test_context(self):
  r=infer_object(compile_knowledge_base(CONFIG),{"object_id":"X","features":{"connected_equipment":["主燃油泵","喷嘴总管"]}}); self.assertEqual(r["system_type"]["label"],"FUEL")
 def test_geometry_unknown(self):
  r=infer_object(compile_knowledge_base(CONFIG),{"object_id":"X","features":{"geometry_object_type":"PIPE","outside_diameter_mm":12}}); self.assertEqual(r["system_type"]["label"],"UNKNOWN")
 def test_graph_gate(self):
  base=[{"object_id":"A","system_type":{"label":"FUEL"},"requires_human_review":False,"review_reasons":[]},{"object_id":"B","system_type":{"label":"UNKNOWN"},"requires_human_review":True,"review_reasons":["X"]}]
  self.assertEqual(propagate_over_graph(base,[{"source_object_id":"A","target_object_id":"B"}])[1]["system_type"]["label"],"UNKNOWN")
  self.assertEqual(propagate_over_graph(base,[{"source_object_id":"A","target_object_id":"B","fluid_continuity_proven":True}])[1]["system_type"]["label"],"FUEL")
if __name__=="__main__": unittest.main()
