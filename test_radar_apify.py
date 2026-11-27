import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class TestBudgetZero(unittest.TestCase):
    def test_il_workflow_non_trasmette_le_credenziali(self):
        workflow = Path(".github/workflows/aggiorna-eventi.yml").read_text(encoding="utf-8")
        self.assertNotIn("secrets.APIFY", workflow)
        self.assertNotIn("vars.APIFY", workflow)

    def test_le_vecchie_variabili_non_avviano_actor(self):
        script = Path("radar_apify.py").resolve()
        env = dict(os.environ, APIFY_TOKEN="test", APIFY_META_AUTORIZZATO="1", APIFY_GOOGLE_AUTORIZZATO="1")
        with TemporaryDirectory() as directory:
            subprocess.run([sys.executable, str(script)], env=env, cwd=directory, check=True, capture_output=True)
            report = json.loads(Path(directory, "apify-rapporto.json").read_text(encoding="utf-8"))
        self.assertEqual(report, {"stato": "disattivato_budget_zero", "budgetUsd": 0, "actorAvviati": 0})
