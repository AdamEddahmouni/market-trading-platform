"""Controlled categorical qualification: synthetic labels, never a market-quality claim."""
import json
from market_platform_foundation.intelligence.inference.local_qualification import SCHEMA
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from tests.support.coverage_universe import strength

class QualificationProvider:
    provider_id="inference.fixture.local"
    model_id="fixture.qualification.v1"
    runtime="FIXTURE"
    def __init__(self,category=None,malformed=False):
        self.category,self.malformed,self.calls=category,malformed,0
    def infer(self,packet,*,rendered_prompt,config):
        self.calls+=1
        c=packet.candidates[0]
        raw={"schema_version":SCHEMA,"instrument_id":c["instrument"]["instrument_id"],
             "category":self.category or ("WARRANTS_REVIEW" if strength(c)>=80 else "NO_SUPPORTED_CASE"),
             "rationale":"The admitted quote and technical observations inform additional review.",
             "supporting_refs":[e["evidence_id"] for e in c["current_market_evidence"] if not e["weak_reasons"]],
             "conflicting_refs":[],"uncertainties":["Interpretation is limited."]}
        return ProviderInferenceResponse("bad json" if self.malformed else json.dumps(raw),
            self.provider_id,self.model_id,simulated=True)

class ExperimentalFixtureAuthority:
    """Explicit test-only reauthorization into an isolated fixture store; never imported by runtime."""
    def __init__(self, repository):
        self.repository=repository
    def admit(self, staged):
        import copy
        assert staged["operationally_approved"] is False and staged["simulated"]
        assert staged["staged"]["local_model"]["runtime"]=="FIXTURE"
        assert staged["staged"]["premium_model"]["runtime"]=="FIXTURE"
        record=copy.deepcopy(staged)
        record.pop("staged")
        record["method"]="EXHAUSTIVE_EXISTING"
        record["run_id"]="CONTROLLED-"+staged["run_id"]
        record["schema_version"]="screener-ai-screener/1.0.0"
        record["fixture_authority"]={"evidence_class":"SOFTWARE_CONTROLLED","experimental_origin":staged["run_id"]}
        for candidate in record["evidence"]:candidate.setdefault("alignments",[])
        self.repository.put("candidate_run",record["run_id"],record)
        return record["run_id"]
