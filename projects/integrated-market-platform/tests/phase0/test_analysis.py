import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.analysis import analyze_tree


class AnalysisTests(unittest.TestCase):
    def test_direct_broker_import_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "strategies").mkdir()
            (root / "strategies" / "bad.py").write_text(
                "import ib_insync\n", encoding="utf-8"
            )
            report = analyze_tree(root)
            self.assertEqual(report["prohibited_edges"][0]["target"], "ib_insync")

    def test_nonconstant_dynamic_import_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.py").write_text(
                "import importlib\nimportlib.import_module(name)\n", encoding="utf-8"
            )
            report = analyze_tree(root)
            self.assertEqual(
                report["dynamic_load_findings"][0]["reason"],
                "NONCONSTANT_DYNAMIC_IMPORT",
            )

    def test_constant_internal_dynamic_import_is_audited_as_a_static_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "loader.py").write_text(
                '__import__("internal.module", fromlist=["Thing"])\n',
                encoding="utf-8",
            )

            report = analyze_tree(root)

            self.assertEqual(report["dynamic_load_findings"], [])
            self.assertIn(
                {"path": "loader.py", "target": "internal.module"},
                report["import_edges"],
            )

    def test_constant_prohibited_dynamic_import_remains_prohibited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "loader.py").write_text(
                '__import__("requests.sessions", fromlist=["Session"])\n',
                encoding="utf-8",
            )

            report = analyze_tree(root)

            self.assertEqual(report["dynamic_load_findings"], [])
            self.assertIn(
                {"path": "loader.py", "target": "requests.sessions"},
                report["prohibited_edges"],
            )

    def test_governed_source_has_no_prohibited_route(self):
        report = analyze_tree(Path("src/market_platform_foundation"))
        self.assertEqual(report["prohibited_edges"], [])
        self.assertEqual(report["unresolved_internal_imports"], [])
        self.assertEqual(report["dynamic_load_findings"], [])
        self.assertTrue(all(not paths for paths in report["prohibited_routes"].values()))


    def test_ctypes_exception_is_limited_to_audited_local_memory_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ordinary = root / "ordinary.py"
            ordinary.write_text("import ctypes\n", encoding="utf-8")
            self.assertEqual(analyze_tree(root)["prohibited_edges"][0]["target"], "ctypes")
            ordinary.unlink()
            bridge = root / "intelligence/inference/local_resources.py"
            bridge.parent.mkdir(parents=True)
            bridge.write_text("import ctypes\nctypes.windll.kernel32.GlobalMemoryStatusEx(None)\n", encoding="utf-8")
            self.assertEqual(analyze_tree(root)["prohibited_edges"], [])
            bridge.write_text("import ctypes\nctypes.windll.kernel32.CreateProcessW(None)\n", encoding="utf-8")
            self.assertEqual(analyze_tree(root)["prohibited_edges"][0]["target"], "ctypes")
            bridge.write_text("from ctypes import WinDLL\n", encoding="utf-8")
            self.assertEqual(analyze_tree(root)["prohibited_edges"][0]["target"], "ctypes")

            for unsafe in (
                "k=ctypes.windll.kernel32; k.CreateProcessW(None)",
                "getattr(ctypes.windll.kernel32,'CreateProcessW')(None)",
                "ctypes.windll.kernel32['CreateProcessW'](None)",
                "query=ctypes.windll.psapi.GetProcessMemoryInfo; other=query; other(None)",
                "native=ctypes; native.windll.kernel32.CreateProcessW(None)",
            ):
                bridge.write_text("import ctypes\n"+unsafe+"\n", encoding="utf-8")
                self.assertEqual(analyze_tree(root)["prohibited_edges"][0]["target"], "ctypes", unsafe)
