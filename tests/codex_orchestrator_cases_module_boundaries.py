import unittest

from tests.codex_orchestrator_module_loader import ROOT


class ModuleBoundariesTests(unittest.TestCase):
    def test_prefect_flow_has_no_cli_dependency(self):
        prefect_flow = ROOT / "scripts" / "_codex_orchestrator" / "native_workflows" / "prefect_flow.py"
        source = prefect_flow.read_text(encoding="utf-8")
        self.assertNotIn("orchestrator_cli", source)
