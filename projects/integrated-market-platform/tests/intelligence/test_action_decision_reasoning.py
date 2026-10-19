"""Model-selected reasoning wire; the canonical validator remains authoritative."""
import copy
import json
import unittest

from market_platform_foundation.intelligence.inference import action_decision as ad
from tests.intelligence.test_action_decision import candidate, proposal, wire, NOW, END


class ReasoningWireTests(unittest.TestCase):
    def setUp(self):
        self.c = candidate()
        self.context = dict(position=dict(state='FLAT', snapshot_at=NOW, pending=False),
                            candidate_valid_until=END, opportunity=None, authority=True, allow_short=False)
        self.conditions = ad.build_conditions(self.c, self.context, NOW)

    def answer(self, state='ENTER'):
        p = json.loads(wire(proposal(state), self.c))
        p.update(schema_version='action-proposal-wire/3.0.0',
                 rationale=dict(basis_refs=['q', 't'], assessment='EVIDENCE_SUFFICIENT'), uncertainties=[])
        return p

    def decode(self, p):
        raw, reason = ad.decode_wire(json.dumps(p), self.c, self.conditions)
        return (None, reason) if reason else ad.parse_proposal(raw, self.c, self.conditions)

    def test_schema_has_no_free_text_reasoning_or_unknown_evidence(self):
        s = ad.reasoned_wire_schema(self.c, self.conditions)['properties']
        self.assertEqual(s['rationale']['type'], 'object')
        self.assertEqual(s['rationale']['properties']['basis_refs']['items']['enum'], ['q', 't'])
        self.assertEqual(s['uncertainties']['items']['enum'], ['MODEL_UNCERTAINTY', 'CONDITION_NOT_MET'])

    def test_model_choices_render_without_values_and_keep_the_decision(self):
        value, reason = self.decode(self.answer())
        self.assertIsNone(reason)
        self.assertEqual(value['proposal_state'], 'ENTER')
        self.assertEqual(value['supporting_refs'], ['q', 't'])
        self.assertIn('quote', value['rationale'])
        self.assertIn('technical', value['rationale'])
        self.assertNotIn('150', value['rationale'])

    def test_model_no_action_and_uncertainty_are_never_upgraded(self):
        p = self.answer('NO_ACTION')
        p['rationale']['assessment'] = 'MODEL_UNCERTAIN'
        p['uncertainties'] = ['MODEL_UNCERTAINTY']
        value, reason = self.decode(p)
        self.assertIsNone(reason)
        self.assertEqual(ad.gate_proposal(value, self.c, self.context, now=NOW)['action_state'], 'NO_ACTION')
        self.assertIn('uncertain', value['rationale'])
        self.assertTrue(value['uncertainties'])

    def test_malformed_claims_and_numeric_or_unicode_injections_fail_closed(self):
        for mutation in [dict(assessment='price 150'), dict(assessment='price １５０'),
                         dict(basis_refs=['unknown']), dict(basis_refs=['q', 'q']),
                         dict(basis_refs=[]), dict(assessment='GUARANTEED'), dict(extra='buy')]:
            p = self.answer()
            p['rationale'].update(mutation)
            self.assertIsNotNone(self.decode(p)[1], mutation)
        p = self.answer(); p['uncertainties'] = ['２']
        self.assertIsNotNone(self.decode(p)[1])

    def test_invalid_action_direction_and_condition_are_still_rejected(self):
        for k, v in [('proposal_state', 'BUY'), ('direction', 'UPSIDE'), ('entry_conditions', ['THESIS_CONTINUES'])]:
            p = self.answer(); p[k] = v
            self.assertIsNotNone(self.decode(p)[1])

    def test_weak_support_and_erased_conflict_remain_rejected(self):
        self.c['reference_evidence'] = [dict(self.c['current_market_evidence'][1], evidence_id='w', weak_reasons=['STALE'])]
        p = self.answer(); p['evidence_stance']['w'] = 'SUPPORTING'
        self.assertEqual(self.decode(p)[1], 'INVALID_SUPPORT')
        self.c['alignments'] = [dict(result='CONFLICTING', sentiment_refs=['t'])]
        p['evidence_stance']['w'] = 'CONTEXT'
        self.assertEqual(self.decode(p)[1], 'NEWS_CONFLICT_NOT_DISCLOSED')

    def test_expired_evidence_and_absent_forecast_cannot_gain_authority(self):
        value, reason = self.decode(self.answer())
        self.assertIsNone(reason)
        fresh = ad.gate_proposal(value, self.c, self.context, now=NOW)
        self.assertIn('NO_GOVERNED_OPPORTUNITY', fresh['blocker_codes'])
        stale = ad.gate_proposal(value, self.c, self.context, now=END)
        self.assertEqual(stale['action_state'], 'REVALIDATION_REQUIRED')

    def test_legacy_free_text_is_validated_unchanged(self):
        p = json.loads(wire(proposal(), self.c))
        for text in ['price 150', 'price １５０', 'Guaranteed profit', 'submit shares']:
            p['rationale'] = text
            self.assertEqual(self.decode(p)[1], 'UNSUPPORTED_EXECUTION_OR_LEVEL')

    def test_unavailable_uncertainty_is_not_invented(self):
        p = self.answer(); p['uncertainties'] = ['MISSING_EVIDENCE']
        self.assertIsNotNone(self.decode(p)[1])

    def test_duplicate_json_keys_cannot_change_a_model_choice(self):
        raw = json.dumps(self.answer()).replace('"assessment": "EVIDENCE_SUFFICIENT"',
            '"assessment": "EVIDENCE_SUFFICIENT", "assessment": "MODEL_UNCERTAIN"')
        self.assertEqual(ad.decode_wire(raw, self.c, self.conditions), (None, 'SCHEMA_INVALID'))

    def test_a_substantive_refusal_cannot_be_rendered_into_an_action(self):
        for assessment in ('EVIDENCE_INSUFFICIENT', 'MODEL_UNCERTAIN'):
            for state in ('ENTER', 'HOLD', 'EXIT'):
                p = self.answer(state)
                p['rationale']['assessment'] = assessment
                self.assertIsNotNone(self.decode(p)[1], (state, assessment))

    def test_every_offered_uncertainty_renders_to_validator_compatible_text(self):
        self.c['missing'] = [dict(capability='ORDER_FLOW')]
        self.c['reference_evidence'] = [dict(self.c['current_market_evidence'][1], evidence_id='w', weak_reasons=['STALE'])]
        self.c['alignments'] = [dict(result='CONFLICTING', sentiment_refs=['t'])]
        self.conditions = ad.build_conditions(self.c, self.context, NOW)
        for code in ad.reasoned_wire_schema(self.c, self.conditions)['properties']['uncertainties']['items']['enum']:
            p = self.answer('NO_ACTION')
            p['evidence_stance'].update(t='CONFLICTING', w='CONTEXT')
            p['uncertainties'] = [code]
            self.assertIsNone(self.decode(p)[1], code)

    def test_no_evidence_schema_has_no_invalid_empty_enum(self):
        self.c['current_market_evidence'] = []
        self.c['reference_evidence'] = []
        self.conditions = ad.build_conditions(self.c, self.context, NOW)
        basis = ad.reasoned_wire_schema(self.c, self.conditions)['properties']['rationale']['properties']['basis_refs']
        self.assertEqual(basis, dict(type='array', maxItems=0))
        p = self.answer('NO_ACTION')
        p['evidence_stance'] = {}
        p['rationale'].update(basis_refs=[], assessment='EVIDENCE_INSUFFICIENT')
        self.assertIsNone(self.decode(p)[1])
