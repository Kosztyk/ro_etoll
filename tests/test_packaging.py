"""RO eToll packaging tests: no Home Assistant runtime or eToll account."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ro_etoll_packaging",ROOT/"tools/check_repository.py")
assert spec and spec.loader
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class PackagingTests(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(checker.inspect_repository(ROOT),[])
    def test_manifest_version(self):
        m=json.loads((ROOT/"custom_components/ro_etoll/manifest.json").read_text())
        self.assertEqual(m["domain"],"ro_etoll")
        self.assertEqual(m["version"],"1.0.2")
        self.assertEqual(m["dependencies"],["binary_sensor","sensor"])
    def test_hacs_name(self):
        h=json.loads((ROOT/"hacs.json").read_text())
        self.assertEqual(h["name"],"RO eToll")
        self.assertTrue(h["render_readme"])

if __name__=="__main__":
    unittest.main()
