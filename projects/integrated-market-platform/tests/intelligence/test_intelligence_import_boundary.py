"""Public intelligence facade contracts and leaf-import isolation."""
import json
import os
import subprocess
import sys
import unittest


class IntelligenceImportBoundaryTests(unittest.TestCase):
    def test_contract_import_does_not_initialize_provider_or_runtime_subsystems(self):
        completed = subprocess.run([
            sys.executable, "-c",
            "import json,sys; from market_platform_foundation.intelligence.contracts import EventV1; "
            "print(json.dumps(sorted(sys.modules)))",
        ], capture_output=True, text=True, check=True, env=dict(os.environ))
        modules = json.loads(completed.stdout)
        for name in ("normalization", "replay", "signals", "scheduling", "snapshots"):
            with self.subTest(name=name):
                self.assertNotIn("market_platform_foundation.intelligence." + name, modules)

    def test_comparison_import_does_not_initialize_the_opportunity_engine(self):
        completed = subprocess.run([
            sys.executable, "-c",
            "import json,sys; from market_platform_foundation.intelligence.opportunity import GlobalOpportunityComparator; "
            "print(json.dumps(sorted(sys.modules)))",
        ], capture_output=True, text=True, check=True, env=dict(os.environ))
        modules = json.loads(completed.stdout)
        self.assertNotIn("market_platform_foundation.intelligence.opportunity.engine", modules)
        self.assertNotIn("market_platform_foundation.intelligence.evaluation", modules)

    def test_public_exports_preserve_original_objects_and_discoverability(self):
        import market_platform_foundation.intelligence as facade
        from market_platform_foundation.intelligence.normalization import normalize_event
        from market_platform_foundation.intelligence.signals import FastSignalEngine
        from market_platform_foundation.intelligence.scheduling import InferenceScheduler
        for name, original in (("normalize_event", normalize_event),
                               ("FastSignalEngine", FastSignalEngine),
                               ("InferenceScheduler", InferenceScheduler)):
            with self.subTest(name=name):
                self.assertIs(getattr(facade, name), original)
                self.assertIs(getattr(facade, name), getattr(facade, name))
        self.assertTrue(set(facade.__all__).issubset(dir(facade)))
        namespace = {}
        exec("from market_platform_foundation.intelligence import *", namespace)
        for name in facade.__all__:
            self.assertIs(namespace[name], getattr(facade, name))
        with self.assertRaises(AttributeError):
            getattr(facade, "_unknown_public_export")

    def test_opportunity_public_exports_preserve_original_objects(self):
        import market_platform_foundation.intelligence.opportunity as facade
        from market_platform_foundation.intelligence.opportunity.comparison import GlobalOpportunityComparator
        from market_platform_foundation.intelligence.opportunity.engine import OpportunityEngine
        self.assertIs(facade.GlobalOpportunityComparator, GlobalOpportunityComparator)
        self.assertIs(facade.OpportunityEngine, OpportunityEngine)
        self.assertTrue(set(facade.__all__).issubset(dir(facade)))
        namespace = {}
        exec("from market_platform_foundation.intelligence.opportunity import *", namespace)
        for name in facade.__all__:
            self.assertIs(namespace[name], getattr(facade, name))
        with self.assertRaises(AttributeError):
            getattr(facade, "_unknown_public_export")

    def test_lazy_export_maps_cover_every_advertised_name_exactly_once(self):
        import importlib
        for package in ("market_platform_foundation.intelligence",
                        "market_platform_foundation.intelligence.opportunity"):
            with self.subTest(package=package):
                facade = importlib.import_module(package)
                grouped = [name for names in facade._EXPORT_GROUPS.values() for name in names]
                self.assertEqual(len(grouped), len(set(grouped)))
                eager = set(facade.__all__) - set(grouped)
                self.assertEqual(set(grouped) | eager, set(facade.__all__))
                self.assertTrue(eager.issubset(vars(facade)))
                for module, names in facade._EXPORT_GROUPS.items():
                    owner = importlib.import_module(module, package)
                    for name in names:
                        self.assertIs(getattr(facade, name), getattr(owner, name))

    def test_facade_resolution_is_independent_of_import_order(self):
        statements = (
            "import market_platform_foundation.intelligence.opportunity.engine as owner; "
            "import market_platform_foundation.intelligence.opportunity as facade",
            "import market_platform_foundation.intelligence.opportunity as facade; "
            "facade.OpportunityEngine; "
            "import market_platform_foundation.intelligence.opportunity.engine as owner",
            "import market_platform_foundation.intelligence.opportunity as facade; "
            "from market_platform_foundation.intelligence import normalize_event; "
            "import market_platform_foundation.intelligence.opportunity.engine as owner",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                subprocess.run([
                    sys.executable, "-c",
                    statement + "; assert facade.OpportunityEngine is owner.OpportunityEngine",
                ], capture_output=True, text=True, check=True, env=dict(os.environ))

    def test_normalization_registration_is_unchanged_when_first_reached_through_facade(self):
        program = (
            "import json; from market_platform_foundation.intelligence.normalization import registry; "
            "print(json.dumps(sorted(map(repr, registry._REGISTRY))))"
        )
        direct = subprocess.run([sys.executable, "-c", program],
                                capture_output=True, text=True, check=True, env=dict(os.environ))
        through_facade = subprocess.run([
            sys.executable, "-c",
            "from market_platform_foundation.intelligence import normalize_event; " + program,
        ], capture_output=True, text=True, check=True, env=dict(os.environ))
        self.assertEqual(direct.stdout, through_facade.stdout)

    def test_facade_attributes_remain_patchable_and_restore_the_original(self):
        from unittest import mock
        import market_platform_foundation.intelligence as facade
        from market_platform_foundation.intelligence.normalization import normalize_event
        sentinel = object()
        with mock.patch("market_platform_foundation.intelligence.normalize_event", sentinel):
            self.assertIs(facade.normalize_event, sentinel)
        self.assertIs(facade.normalize_event, normalize_event)

    def test_model_packages_and_backend_api_import_without_scientific_stack(self):
        program = (
            "import json,sys; "
            "import market_platform_foundation.intelligence.fusion, "
            "market_platform_foundation.intelligence.baselines, "
            "market_platform_foundation.intelligence.production, "
            "market_platform_foundation.intelligence.training.factory, "
            "tools.ui1.run_ui_api; "
            "print(json.dumps(sorted({name.split('.')[0] for name in sys.modules})))"
        )
        completed = subprocess.run([sys.executable, "-c", program],
                                   capture_output=True, text=True, check=True, env=dict(os.environ))
        packages = json.loads(completed.stdout)
        for name in ("sklearn", "scipy", "pandas", "joblib"):
            with self.subTest(name=name):
                self.assertNotIn(name, packages)
