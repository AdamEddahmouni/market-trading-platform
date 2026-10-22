"""A harness-built AI Screener result carried through the production run registry.

Acceptance harnesses build the stored candidate run themselves. Routing it through the real registry
means the browser still follows the production contract: POST returns a run at once and the result
is read from the real status routes.
"""
from market_platform_foundation.ui_api import screener_ai_runs


def start_controlled_run(account_id, scope, build, *, engine=None):
    """Start a run whose work is ``build(scope)``; status and result are then read from the real routes."""

    class Controlled:
        def validate_scope(self, body):
            return body

        def engine(self):
            return dict(dict(provider_id='controlled.fixture', model_id='controlled', runtime='LOCAL_MODEL'), **(engine or {}), timeout_seconds=45)

        def ai_status(self):
            return dict(self.engine(), state='AVAILABLE', reason=None, budget=None)

        def run(self, body):
            return build(body)

    screener_ai_runs._RUNS = screener_ai_runs.AiScreenerRuns(Controlled())
    return screener_ai_runs._RUNS.start(account_id, scope)
