"""AI Screener provider contract: prompt/schema agreement, per-model Claude requests, and the full-intake round trip.

Every HTTP call is an intercepted transport: no network, no key, no spend."""
import json
import re
import unittest
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

from market_platform_foundation.intelligence.inference import candidate_reduction
from market_platform_foundation.intelligence.inference.anthropic_models import (
    CLAUDE_MODELS, COUNT_EXCLUDED, SYSTEM, SYSTEM_TOOL_REQUIRED, THINKING_HEADROOM, TOOL_NAME, UNSUPPORTED,
    ModelRequestContractUnsupported, build_request, contract_status, count_request,
)
from market_platform_foundation.intelligence.inference.anthropic_synthesis import (
    COUNT_TOKENS_URL, DEFAULT_MODEL, AnthropicSynthesisProvider, BudgetedProvider, DailyBudget, rejection_reason,
)
from market_platform_foundation.intelligence.inference.candidate_reduction import (
    MAX_INTAKE, MAX_PACKET_BYTES, MAX_SELECTED, PROMPT_ID, SCHEMA_VERSION, WIRE_SCHEMA_VERSION, CandidateReducer,
    ScreenerEvidencePacket, output_schema, packet_candidates, parse_reduction, reference_ids,
)
from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
from market_platform_foundation.intelligence.inference.local_provider import select_synthesis_provider
from market_platform_foundation.intelligence.inference.prompts import PromptRegistry
from market_platform_foundation.intelligence.inference.synthesis_engines import ENGINE_SPECS, engine_options
from market_platform_foundation.ui_api.screener_news_evidence import attach_news, fit_news, project_news
from tests.intelligence.test_news_candidate_evidence import NEWS_ISO, grounded
from tests.platform.test_screener_s11 import FINVIZ, finviz_row, service

REDUCTION = IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION
CLOCK = datetime.fromisoformat(NEWS_ISO.replace('Z', '+00:00')).timestamp()
OCTOBER_7_MODEL = 'claude-haiku-4-5-20251001'
SELECTABLE = [model for model, _ in ENGINE_SPECS['anthropic'].models]
V1_HASH = '23b28ee3d1ca585a026773a75623345c352027df34a8dc64701b6027d35cf17e'
V2_HASH = '8e270de1db72b892a29eae30d6fcbe215e706ac08ddc191e854f18d3d6e31d3e'


def packed(count=MAX_INTAKE, *, fit=True):
    """``count`` grounded candidates, each with three long stories; (candidates, news projections)."""
    rows = [{'instrument': {'instrument_id': f'EQ:X{i}'}, 'symbol': f'X{i}', 'company': f'Example company {i}'} for i in range(count)]
    items = [finviz_row(f'Example company {i} announces event {j} ' + 'x' * 300, [f'X{i}'], f'2026-09-28 09:{j + 30:02d}:00',
                        f'https://fixture.test/{i}/{j}') for i in range(count) for j in range(3)]
    values = project_news(service(finviz={**FINVIZ, 'items': items}), universe='US_EQUITIES', rows=rows, refresh=True)
    candidates = [grounded(row['instrument']['instrument_id']) for row in rows]
    for c in candidates:
        attach_news(c, values[c['instrument']['instrument_id']], now=NEWS_ISO)
    if fit:
        fit_news({}, candidates, values, now=NEWS_ISO)
    return candidates, values


def packet_bytes(candidates):
    return len(json.dumps(dict(scope={}, decision_cutoff=NEWS_ISO, candidates=packet_candidates(candidates)),
                          ensure_ascii=False, sort_keys=True).encode('utf-8'))


def wire_pick(candidates, key, rank):
    """A valid compact pick: the current quote and technicals, plus every conflict the packet requires."""
    c = candidates[key]
    own = reference_ids(c)
    conflicts = sorted({own.index(ref) for item in c.get('alignments', []) if item['result'] == 'CONFLICTING' for ref in item['sentiment_refs']})
    return {'candidate_key': key, 'rank': rank, 'rationale': 'Review candidate grounded in admitted observations.',
            'supporting_refs': [0, 1], 'conflicting_refs': conflicts, 'uncertainties': ['Coverage is limited.']}


def wire_output(candidates, keys):
    return {'schema_version': SCHEMA_VERSION, 'candidates': [wire_pick(candidates, key, rank) for rank, key in enumerate(keys, 1)],
            'limitations': ['Candidate reduction only.']}


class Claude:
    """Messages and token-count stand-in that records every request it is sent."""

    def __init__(self, answer=None, *, content=None, status=200, message='', stop_reason='tool_use', input_tokens=1234):
        self.answer, self.content, self.status, self.message = answer, content, status, message
        self.stop_reason, self.input_tokens, self.requests = stop_reason, input_tokens, []

    def __call__(self, url, body, headers, timeout):
        request = json.loads(body.decode('utf-8'))
        self.requests.append((url, request, body, timeout))
        if self.status != 200:
            return self.status, json.dumps({'type': 'error', 'error': {'type': 'invalid_request_error', 'message': self.message}}).encode()
        if url == COUNT_TOKENS_URL:
            return 200, json.dumps({'input_tokens': self.input_tokens}).encode()
        content = self.content
        if content is None:
            content = [{'type': 'tool_use', 'id': 't1', 'name': TOOL_NAME, 'input': self.answer}]
            if CLAUDE_MODELS[request['model']].thinks_by_default:
                content.insert(0, {'type': 'thinking', 'thinking': '', 'signature': 's'})
        return 200, json.dumps({'id': 'msg_1', 'stop_reason': self.stop_reason, 'content': content,
                                'usage': {'input_tokens': self.input_tokens, 'output_tokens': 300}}).encode()


def reduce_with(model, transport, candidates):
    provider = AnthropicSynthesisProvider(api_key='controlled', model=model, poster=transport)
    reducer = CandidateReducer(provider=provider, clock=lambda: CLOCK)
    return reducer.reduce({}, candidates, NEWS_ISO), reducer


class PromptSchemaAgreementTests(unittest.TestCase):
    """Prompt v3 may name only fields the model can emit or fields the packet really carries."""

    def setUp(self):
        self.candidates, _ = packed(3)
        self.schema = output_schema(self.candidates)
        self.prompt = PromptRegistry().get_by_id(PROMPT_ID)

    def schema_fields(self):
        item = self.schema['properties']['candidates']['items']
        return set(self.schema['properties']), set(item['properties'])

    def packet_keys(self):
        found = {'scope', 'decision_cutoff', 'candidates'}

        def walk(value):
            if isinstance(value, dict):
                found.update(value)
                for inner in value.values():
                    walk(inner)
            elif isinstance(value, list):
                for inner in value:
                    walk(inner)
        walk(packet_candidates(self.candidates))
        return found

    @staticmethod
    def declared(template, label):
        line = re.search(rf'^{label} fields, and no others: (.+)\.$', template, re.M)
        return {name.strip() for name in line.group(1).split(',')} if line else None

    @staticmethod
    def named_fields(template):
        prose = template.replace('{{output_schema}}', '').replace('{{evidence_json}}', '')
        return set(re.findall(r'\b[a-z]+(?:_[a-z0-9]+)+\b', prose))

    def test_production_prompt_is_v3_and_declares_exactly_the_wire_schema_fields(self):
        self.assertEqual((self.prompt.prompt_id, self.prompt.version), ('screener.ai_candidate_reduction.v3', '3.0.0'))
        top, item = self.schema_fields()
        self.assertEqual(self.declared(self.prompt.template, 'Output'), top)
        self.assertEqual(self.declared(self.prompt.template, 'Candidate'), item)
        self.assertEqual(item, set(candidate_reduction.WIRE_KEYS))
        self.assertEqual(set(self.schema['required']), top)
        self.assertEqual(set(self.schema['properties']['candidates']['items']['required']), item)

    def test_every_field_named_in_prompt_prose_is_emitted_or_carried_by_the_packet(self):
        top, item = self.schema_fields()
        unknown = self.named_fields(self.prompt.template) - top - item - self.packet_keys()
        self.assertEqual(unknown, set(), 'the prompt names fields that exist in neither the wire schema nor the packet')

    def test_the_check_catches_the_historical_v2_drift(self):
        top, item = self.schema_fields()
        v2 = PromptRegistry().get_by_id('screener.ai_candidate_reduction.v2')
        drift = self.named_fields(v2.template) - top - item - self.packet_keys()
        self.assertEqual(drift, {'weak_refs', 'missing_capabilities'})
        self.assertIsNone(self.declared(v2.template, 'Output'))

    def test_historical_prompts_are_unchanged(self):
        registry = PromptRegistry()
        self.assertEqual(registry.get_by_id('screener.ai_candidate_reduction.v1').content_hash, V1_HASH)
        self.assertEqual(registry.get_by_id('screener.ai_candidate_reduction.v2').content_hash, V2_HASH)


class ModelCapabilityTests(unittest.TestCase):
    def test_every_selectable_claude_model_has_a_row_and_can_run_the_ai_screener(self):
        self.assertEqual(set(SELECTABLE), set(CLAUDE_MODELS))
        self.assertIn(OCTOBER_7_MODEL, SELECTABLE)
        self.assertIn(DEFAULT_MODEL, SELECTABLE)
        for model in SELECTABLE:
            with self.subTest(model=model):
                self.assertEqual(contract_status(model, REDUCTION),
                                 {'supported': True, 'reason': None, 'selected_model': model,
                                  'required_contract': 'STRICT_TOOL_SCHEMA', 'unsupported_capability': None})

    def test_a_model_with_no_row_is_refused_with_the_model_contract_and_capability(self):
        for model in ('claude-fable-5-1', 'claude-sonnet-4-6', 'claude-haiku-4-5', ''):
            with self.subTest(model=model):
                self.assertEqual(contract_status(model, REDUCTION),
                                 {'supported': False, 'reason': UNSUPPORTED, 'selected_model': model,
                                  'required_contract': 'STRICT_TOOL_SCHEMA', 'unsupported_capability': 'MODEL_NOT_IN_CAPABILITY_TABLE'})
                with self.assertRaises(ModelRequestContractUnsupported):
                    build_request(model, task_type=REDUCTION, input_schema={}, rendered_prompt='p', max_tokens=10)

    def test_a_model_without_strict_schemas_is_refused_for_the_ai_screener_only(self):
        loose = replace(CLAUDE_MODELS[OCTOBER_7_MODEL], strict_tools=False)
        with patch.dict(CLAUDE_MODELS, {OCTOBER_7_MODEL: loose}):
            status = contract_status(OCTOBER_7_MODEL, REDUCTION)
            self.assertEqual((status['supported'], status['unsupported_capability']), (False, 'STRICT_TOOL_SCHEMA'))
            # A task whose contract is not strict stays usable on that model.
            self.assertTrue(contract_status(OCTOBER_7_MODEL, IntelligenceTaskType.NEWS_SCREENER_SYNTHESIS)['supported'])
            body = build_request(OCTOBER_7_MODEL, task_type=IntelligenceTaskType.NEWS_SCREENER_SYNTHESIS, input_schema={},
                                 rendered_prompt='p', max_tokens=10)
            self.assertNotIn('strict', body['tools'][0])


class RequestConstructionTests(unittest.TestCase):
    """The exact outgoing body for every selectable Claude model, at the full 50-candidate intake."""

    @classmethod
    def setUpClass(cls):
        cls.candidates, _ = packed()
        cls.answer = wire_output(cls.candidates, range(MAX_SELECTED))

    def expected(self, model, reducer):
        _, rendered, _, _ = reducer._prepare({}, self.candidates, NEWS_ISO)
        tool = {'name': TOOL_NAME, 'description': 'Record the grounded synthesis of the supplied evidence.',
                'input_schema': output_schema(self.candidates), 'strict': True}
        messages = [{'role': 'user', 'content': rendered}]
        if model == OCTOBER_7_MODEL:
            return {'model': model, 'max_tokens': 2600, 'temperature': 0, 'system': SYSTEM, 'messages': messages,
                    'tools': [tool], 'tool_choice': {'type': 'tool', 'name': TOOL_NAME}}
        return {'model': model, 'max_tokens': 2600 + THINKING_HEADROOM, 'system': SYSTEM_TOOL_REQUIRED, 'messages': messages,
                'tools': [tool], 'tool_choice': {'type': 'auto', 'disable_parallel_tool_use': True}}

    def test_exact_generation_request_for_every_selectable_model(self):
        for model in SELECTABLE:
            with self.subTest(model=model):
                transport = Claude(self.answer)
                result, reducer = reduce_with(model, transport, self.candidates)
                self.assertEqual((result['state'], result['reason'], result['model_id']), ('CURRENT', None, model))
                self.assertEqual(len(transport.requests), 1)
                url, body, _, timeout = transport.requests[0]
                self.assertEqual((url, timeout), ('https://api.anthropic.com/v1/messages', 45))
                self.assertEqual(body, self.expected(model, reducer))

    def test_models_that_reject_them_are_sent_no_temperature_and_no_forced_tool(self):
        for model in ('claude-sonnet-5-5', 'claude-opus-5-5'):
            with self.subTest(model=model):
                transport = Claude(self.answer)
                reduce_with(model, transport, self.candidates)
                body = transport.requests[0][1]
                self.assertEqual(set(body), {'model', 'max_tokens', 'system', 'messages', 'tools', 'tool_choice'})
                self.assertEqual(body['tool_choice']['type'], 'auto')
                self.assertIn(f'calling the {TOOL_NAME} tool exactly once', body['system'])
                self.assertTrue(body['tools'][0]['strict'])

    def test_october_7_model_request_keeps_its_historical_shape(self):
        transport = Claude(self.answer)
        _, reducer = reduce_with(OCTOBER_7_MODEL, transport, self.candidates)
        _, rendered, _, _ = reducer._prepare({}, self.candidates, NEWS_ISO)
        # The body the provider built before requests became model-aware, field for field and in order.
        historical = {
            'model': OCTOBER_7_MODEL, 'max_tokens': 2600, 'temperature': 0,
            'system': 'You write grounded evidence syntheses. Use only the supplied packet and record the result with the tool.',
            'messages': [{'role': 'user', 'content': rendered}],
            'tools': [{'name': 'record_synthesis', 'description': 'Record the grounded synthesis of the supplied evidence.',
                       'input_schema': output_schema(self.candidates), 'strict': True}],
            'tool_choice': {'type': 'tool', 'name': 'record_synthesis'},
        }
        self.assertEqual(transport.requests[0][2], json.dumps(historical).encode('utf-8'))

    def test_news_synthesis_request_is_model_aware_and_not_strict(self):
        from tests.intelligence.test_anthropic_synthesis_budget import FakeClaude, run
        from tests.intelligence.test_local_synthesis_provider import grounded as grounded_synthesis
        from market_platform_foundation.intelligence.inference.screener_synthesis import ScreenerSynthesizer
        for model in SELECTABLE:
            with self.subTest(model=model):
                transport = FakeClaude(tool_input=lambda ids: grounded_synthesis(ids))
                provider = AnthropicSynthesisProvider(api_key='controlled', model=model, poster=transport)
                result = run(ScreenerSynthesizer(provider=provider, clock=lambda: 1_790_000_000.0))
                self.assertEqual((result['state'], result['model_id']), ('CURRENT', model))
                body = transport.requests[0][1]
                forced = CLAUDE_MODELS[model].forced_tool_choice
                self.assertEqual('temperature' in body, CLAUDE_MODELS[model].temperature)
                self.assertEqual(body['tool_choice']['type'], 'tool' if forced else 'auto')
                self.assertEqual(body['max_tokens'], 2048 + (0 if forced else THINKING_HEADROOM))
                self.assertNotIn('strict', body['tools'][0])

    def test_unsupported_model_is_refused_before_any_request_and_never_replaced(self):
        transport = Claude(self.answer)
        budget = DailyBudget(None, clock=lambda: CLOCK)
        provider = BudgetedProvider(AnthropicSynthesisProvider(api_key='controlled', model='claude-fable-5-1', poster=transport), budget)
        result = CandidateReducer(provider=provider, clock=lambda: CLOCK).reduce({}, self.candidates, NEWS_ISO)
        self.assertEqual((result['state'], result['reason'], result['model_id']), ('UNAVAILABLE', UNSUPPORTED, 'claude-fable-5-1'))
        self.assertEqual(result['compatibility'], {'selected_model': 'claude-fable-5-1', 'required_contract': 'STRICT_TOOL_SCHEMA',
                                                   'unsupported_capability': 'MODEL_NOT_IN_CAPABILITY_TABLE'})
        self.assertEqual((transport.requests, budget.status()['requests'], budget.status()['tokens']), ([], 0, 0))
        self.assertEqual(result['candidates'], [])
        # The provider itself refuses too, for a caller that does not ask first.
        packet = ScreenerEvidencePacket(REDUCTION, 'run', 'hash', NEWS_ISO, {}, self.candidates, output_schema(self.candidates))
        response = provider.infer(packet, rendered_prompt='p', config=CandidateReducer().config)
        self.assertEqual((response.error_message, response.model_id, transport.requests), (UNSUPPORTED, 'claude-fable-5-1', []))

    def test_a_reply_without_the_tool_call_is_never_parsed_as_text(self):
        prose = [{'type': 'text', 'text': json.dumps(self.answer)}]
        transport = Claude(content=prose, stop_reason='end_turn')
        result, _ = reduce_with('claude-sonnet-5-5', transport, self.candidates)
        self.assertEqual((result['state'], result['reason'], result['candidates']), ('UNAVAILABLE', 'ANTHROPIC_TOOL_NOT_CALLED', []))
        self.assertEqual(result['model_id'], 'claude-sonnet-5-5')
        refused = Claude(content=[], stop_reason='refusal')
        self.assertEqual(reduce_with('claude-opus-5-5', refused, self.candidates)[0]['reason'], 'ANTHROPIC_REFUSAL')
        twice = [{'type': 'tool_use', 'id': 'a', 'name': TOOL_NAME, 'input': self.answer}] * 2
        self.assertEqual(reduce_with('claude-opus-5-5', Claude(content=twice), self.candidates)[0]['reason'], 'ANTHROPIC_RESPONSE_MALFORMED')

    def test_reasoning_room_is_reserved_against_the_daily_budget(self):
        config = CandidateReducer().config
        for model in SELECTABLE:
            provider = BudgetedProvider(AnthropicSynthesisProvider(api_key='controlled', model=model, poster=Claude(self.answer)),
                                        DailyBudget(None))
            extra = THINKING_HEADROOM if CLAUDE_MODELS[model].thinks_by_default else 0
            self.assertEqual(provider.worst_case_tokens('x' * 300, config), 101 + 1500 + 2600 + extra)

    def test_a_saved_model_outside_the_catalog_selects_no_provider(self):
        import tempfile
        from pathlib import Path
        values = {'ANTHROPIC_API_KEY': 'controlled'}
        with tempfile.TemporaryDirectory() as directory:
            chosen = select_synthesis_provider(values.get, cache_dir=Path(directory), engine='anthropic', model='claude-retired-1')
            self.assertEqual((chosen.provider, chosen.reason), (None, 'SYNTHESIS_MODEL_NOT_IN_CATALOG'))
            default = select_synthesis_provider(values.get, cache_dir=Path(directory), engine='anthropic')
            self.assertEqual(default.provider.model_id, DEFAULT_MODEL)
            for model in SELECTABLE:
                picked = select_synthesis_provider(values.get, cache_dir=Path(directory), engine='anthropic', model=model)
                self.assertEqual(picked.provider.model_id, model)


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates, _ = packed()

    def preflight(self, model, transport):
        provider = BudgetedProvider(AnthropicSynthesisProvider(api_key='controlled', model=model, poster=transport), DailyBudget(None))
        reducer = CandidateReducer(provider=provider, clock=lambda: CLOCK)
        digest, rendered, _, _ = reducer._prepare({}, self.candidates, NEWS_ISO)
        packet = ScreenerEvidencePacket(REDUCTION, 'run', digest, NEWS_ISO, {}, self.candidates, output_schema(self.candidates))
        generation = provider._provider.request_body(packet, rendered_prompt=rendered, config=reducer.config)
        return provider.preflight(packet, rendered_prompt=rendered, config=reducer.config), generation, provider

    def test_token_count_request_is_the_generation_request_minus_fields_the_endpoint_does_not_take(self):
        self.assertEqual(COUNT_EXCLUDED, ('max_tokens', 'temperature'))
        for model in SELECTABLE:
            with self.subTest(model=model):
                transport = Claude(input_tokens=150_000)
                result, generation, provider = self.preflight(model, transport)
                (url, counted, _, _), = transport.requests
                self.assertEqual(url, COUNT_TOKENS_URL)
                self.assertEqual(counted, {k: v for k, v in generation.items() if k not in COUNT_EXCLUDED})
                self.assertEqual(counted, count_request(generation))
                for same in ('model', 'system', 'messages', 'tools', 'tool_choice'):
                    self.assertEqual(counted[same], generation[same])
                self.assertEqual(result, {'model_id': model, 'accepted': True, 'input_tokens': 150_000,
                                          'context_window': CLAUDE_MODELS[model].context_window, 'context_fit': True, 'reason': None})
                self.assertEqual(provider.budget_status()['requests'], 0)

    def test_context_fit_counts_the_output_bound_against_the_models_window(self):
        result, _, _ = self.preflight(OCTOBER_7_MODEL, Claude(input_tokens=199_000))
        self.assertEqual((result['accepted'], result['context_fit'], result['reason']), (True, False, 'ANTHROPIC_CONTEXT_EXCEEDED'))
        self.assertTrue(self.preflight('claude-sonnet-5-5', Claude(input_tokens=199_000))[0]['context_fit'])

    def test_provider_rejections_are_classified_without_keeping_the_message(self):
        cases = [
            ('tool_choice: type "tool" and "any" are not supported for this model.', 'ANTHROPIC_TOOL_CHOICE_UNSUPPORTED'),
            ('temperature: non-default values are not supported for this model', 'ANTHROPIC_PARAMETER_UNSUPPORTED'),
            ('The compiled grammar is too large.', 'ANTHROPIC_GRAMMAR_TOO_LARGE'),
            ('tools.0.custom: Schema is too complex for compilation.', 'ANTHROPIC_GRAMMAR_TOO_LARGE'),
            ("tools.0.custom.input_schema: 'const' with a complex value is not supported", 'ANTHROPIC_SCHEMA_REJECTED'),
            ('prompt is too long: 250000 tokens > 200000 maximum', 'ANTHROPIC_CONTEXT_EXCEEDED'),
            ('Your credit balance is too low', 'ANTHROPIC_INVALID_REQUEST_ERROR'),
        ]
        for message, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(rejection_reason(400, {'error': {'type': 'invalid_request_error', 'message': message}}), expected)
                result, _, _ = self.preflight(OCTOBER_7_MODEL, Claude(status=400, message=message))
                self.assertEqual((result['accepted'], result['reason']), (False, expected))
                self.assertNotIn(message, json.dumps(result))
                generated, _ = reduce_with(OCTOBER_7_MODEL, Claude(status=400, message=message), self.candidates)
                self.assertEqual((generated['state'], generated['reason']), ('UNAVAILABLE', expected))
                self.assertNotIn(message, json.dumps(generated))

    def test_unsupported_model_preflight_sends_nothing(self):
        transport = Claude()
        provider = AnthropicSynthesisProvider(api_key='controlled', model='claude-fable-5-1', poster=transport)
        packet = ScreenerEvidencePacket(REDUCTION, 'run', 'hash', NEWS_ISO, {}, self.candidates, output_schema(self.candidates))
        result = provider.preflight(packet, rendered_prompt='p', config=CandidateReducer().config)
        self.assertEqual((result['accepted'], result['reason'], result['unsupported_capability'], transport.requests),
                         (False, UNSUPPORTED, 'MODEL_NOT_IN_CAPABILITY_TABLE', []))


class FullIntakeRoundTripTests(unittest.TestCase):
    def test_raw_packet_exceeds_the_cap_and_the_fitter_brings_it_under_keeping_evidence(self):
        raw, _ = packed(fit=False)
        self.assertGreater(packet_bytes(raw), MAX_PACKET_BYTES)
        with self.assertRaisesRegex(ValueError, 'EVIDENCE_PACKET_BOUND_EXCEEDED'):
            CandidateReducer().estimate({}, raw, NEWS_ISO)
        fitted, _ = packed()
        again, _ = packed()
        self.assertEqual(fitted, again, 'fitting is deterministic')
        self.assertLessEqual(packet_bytes(fitted), MAX_PACKET_BYTES)
        self.assertEqual(CandidateReducer().estimate({}, fitted, NEWS_ISO)['packet_bytes'], packet_bytes(fitted))
        for before, after in zip(raw, fitted):
            self.assertEqual(before['current_market_evidence'], after['current_market_evidence'])
            self.assertTrue(after['sufficient'])
        kept = sum(c['news']['story_count'] for c in fitted)
        self.assertTrue(0 < kept < sum(c['news']['story_count'] for c in raw), 'stories are thinned, never emptied')
        self.assertTrue(any(e['capability'] == 'NEWS' for c in fitted for e in c['reference_evidence']))

    def test_schema_is_valid_and_bounded_at_every_intake_size(self):
        sizes = {}
        for count in (1, 5, 20, MAX_INTAKE):
            with self.subTest(count=count):
                candidates, _ = packed(count)
                schema = output_schema(candidates)
                text = json.dumps(schema)
                sizes[count] = len(text)
                for forbidden in ('anyOf', 'oneOf', 'allOf', '$ref', 'const', 'EQ:', 'EV:', 'weak_refs', 'missing_capabilities'):
                    self.assertNotIn(forbidden, text)
                item = schema['properties']['candidates']['items']['properties']
                self.assertEqual(item['candidate_key']['enum'], list(range(count)))
                self.assertEqual(item['supporting_refs']['items']['enum'], list(range(max(len(reference_ids(c)) for c in candidates))))
                parsed, reason = parse_reduction(json.dumps(wire_output(candidates, range(min(count, MAX_SELECTED)))), candidates)
                self.assertIsNone(reason)
                self.assertEqual(len(parsed['candidates']), min(count, MAX_SELECTED))
        self.assertLess(sizes[MAX_INTAKE], 3000)
        self.assertLess(sizes[MAX_INTAKE] - sizes[1], 4 * MAX_INTAKE)

    def test_fifty_candidates_round_trip_to_at_most_five_canonical_candidates(self):
        candidates, _ = packed()
        keys = [41, 7, 0, 49, 23]
        for model in SELECTABLE:
            with self.subTest(model=model):
                result, _ = reduce_with(model, Claude(wire_output(candidates, keys)), candidates)
                self.assertEqual((result['state'], result['reason'], result['coverage']['candidate_intake']), ('CURRENT', None, MAX_INTAKE))
                self.assertEqual((result['schema_version'], result['wire_schema_version'], result['prompt_id'], result['prompt_version']),
                                 (SCHEMA_VERSION, WIRE_SCHEMA_VERSION, PROMPT_ID, '3.0.0'))
                self.assertEqual(len(result['candidates']), MAX_SELECTED)
                for pick, key in zip(result['candidates'], keys):
                    c = candidates[key]
                    own = reference_ids(c)
                    # The stored pick is the existing canonical shape, with full ids and the packet's own lists.
                    self.assertEqual(set(pick), {'instrument_id', 'rank', 'rationale', 'supporting_refs', 'conflicting_refs',
                                                 'weak_refs', 'missing_capabilities', 'uncertainties'})
                    self.assertEqual(pick['instrument_id'], c['instrument']['instrument_id'])
                    self.assertEqual(pick['supporting_refs'], own[:2])
                    self.assertTrue(set(pick['supporting_refs']) | set(pick['conflicting_refs']) <= set(own))
                    self.assertEqual(pick['missing_capabilities'], sorted({x['capability'] for x in c['missing']}))
                    self.assertEqual(pick['weak_refs'], sorted(x['evidence_id'] for x in c['weak']))

    def test_weak_and_missing_lists_decode_to_exactly_what_the_packet_represents(self):
        candidates, _ = packed(5)
        quality = grounded('EQ:WEAK')
        from market_platform_foundation.intelligence.inference.candidate_reduction import build_candidate
        from market_platform_foundation.market_data.freshness_contract import evaluate
        status = evaluate(capability='squeeze', source='IMP_TEST', delivery_mode='REALTIME', now=NEWS_ISO, as_of=NEWS_ISO,
                          stale_after_ms=30000, policy='CONTROLLED', basis='EVENT_TIME')
        quote = quality['current_market_evidence'][0]
        weak = build_candidate({'instrument_id': 'EQ:WEAK', 'symbol': 'WEAK'}, [
            ('QUOTE', status, quote['facts'], []), ('TECHNICALS', status, {'change_pct': 1.0}, []),
            ('SQUEEZE', status, {'score': 1}, ['LOW_SAMPLE']), ('OPTIONS', status, {'put_call': 1.1}, ['THIN_CHAIN'])], now=NEWS_ISO)
        candidates.append(weak)
        parsed, reason = parse_reduction(json.dumps(wire_output(candidates, [5])), candidates)
        self.assertIsNone(reason)
        stored = parsed['candidates'][0]
        packet = packet_candidates(candidates)[5]
        # Missing: exactly the capabilities the packet lists as missing for this candidate, none invented.
        self.assertEqual(stored['missing_capabilities'], sorted(x['capability'] for x in packet['missing']))
        self.assertNotIn('SQUEEZE', stored['missing_capabilities'])
        # Weak: exactly the packet evidence carrying weak_reasons, the same set the legacy wire had to echo.
        listed = [*packet['current_market_evidence'], *packet['reference_evidence']]
        self.assertEqual(stored['weak_refs'], sorted(e['evidence_id'] for e in listed if e['weak_reasons']))
        self.assertEqual(set(stored['weak_refs']), {x['evidence_id'] for x in packet['weak']})
        self.assertEqual(len(stored['weak_refs']), 2)
        legacy = {**stored}
        self.assertEqual(parse_reduction(json.dumps({'schema_version': SCHEMA_VERSION, 'candidates': [legacy], 'limitations': ['x']}), candidates)[1], None)

    def test_invalid_outputs_are_rejected_with_a_reason_and_never_raise(self):
        candidates, values = packed()
        own = len(reference_ids(candidates[0]))
        largest = max(range(MAX_INTAKE), key=lambda i: len(reference_ids(candidates[i])))
        smallest = min(range(MAX_INTAKE), key=lambda i: len(reference_ids(candidates[i])))
        self.assertLess(len(reference_ids(candidates[smallest])), len(reference_ids(candidates[largest])))
        other_only = len(reference_ids(candidates[largest])) - 1        # admitted by the schema enum, not the small candidate's
        raw, _ = packed(fit=False)
        dropped = len(reference_ids(raw[smallest])) - 1                 # existed before packing, removed by the fitter
        self.assertGreaterEqual(dropped, len(reference_ids(candidates[smallest])))

        def bad(**change):
            return {**wire_pick(candidates, 0, 1), **change}
        cases = [
            ('negative index', bad(supporting_refs=[0, -1]), 'WIRE_REFERENCE_INDEX_INVALID', 'DECODE'),
            ('out-of-range index', bad(supporting_refs=[0, own]), 'WIRE_REFERENCE_INDEX_INVALID', 'DECODE'),
            ('index of another candidate', {**wire_pick(candidates, smallest, 1), 'supporting_refs': [0, other_only]}, 'WIRE_REFERENCE_INDEX_INVALID', 'DECODE'),
            ('evidence omitted during packing', {**wire_pick(candidates, smallest, 1), 'conflicting_refs': [dropped]}, 'WIRE_REFERENCE_INDEX_INVALID', 'DECODE'),
            ('duplicate reference', bad(supporting_refs=[0, 1, 1]), 'INVALID_SUPPORTING_REFS', 'CANONICAL_VALIDATION'),
            ('unknown candidate key', bad(candidate_key=MAX_INTAKE), 'WIRE_CANDIDATE_KEY_INVALID', 'DECODE'),
            ('symbol in place of the key', bad(candidate_key='X0'), 'WIRE_CANDIDATE_KEY_INVALID', 'DECODE'),
            ('instrument id in place of the key', bad(candidate_key='EQ:X0'), 'WIRE_CANDIDATE_KEY_INVALID', 'DECODE'),
            ('numeric string key', bad(candidate_key='0'), 'WIRE_CANDIDATE_KEY_INVALID', 'DECODE'),
            ('fractional key', bad(candidate_key=0.5), 'WIRE_CANDIDATE_KEY_INVALID', 'DECODE'),
            ('structured key', bad(candidate_key={'index': 0}), 'WIRE_CANDIDATE_KEY_INVALID', 'DECODE'),
            ('evidence id in place of an index', bad(supporting_refs=[0, reference_ids(candidates[0])[1]]), 'WIRE_REFERENCE_INDEX_INVALID', 'DECODE'),
            ('key and instrument id together', bad(instrument_id='EQ:X0'), 'SCHEMA_INVALID', 'CANONICAL_VALIDATION'),
            ('restated missing list', bad(missing_capabilities=[]), 'SCHEMA_INVALID', 'CANONICAL_VALIDATION'),
            ('missing binding', {k: v for k, v in wire_pick(candidates, 0, 1).items() if k != 'candidate_key'}, 'SCHEMA_INVALID', 'CANONICAL_VALIDATION'),
            ('pick is not an object', [0, 1], 'SCHEMA_INVALID', 'CANONICAL_VALIDATION'),
        ]
        for label, pick, expected, stage in cases:
            with self.subTest(label):
                answer = {'schema_version': SCHEMA_VERSION, 'candidates': [pick], 'limitations': ['x']}
                self.assertEqual(parse_reduction(json.dumps(answer), candidates), (None, expected))
                result, _ = reduce_with(OCTOBER_7_MODEL, Claude(answer), candidates)
                self.assertEqual((result['state'], result['reason'], result['candidates']), ('INVALID_OUTPUT', expected, []))
                self.assertEqual(result['validation']['stage'], stage)
                self.assertEqual(result['model_id'], OCTOBER_7_MODEL)
        six = wire_output(candidates, range(MAX_SELECTED + 1))
        self.assertEqual(reduce_with(OCTOBER_7_MODEL, Claude(six), candidates)[0]['reason'], 'CANDIDATE_BOUND_EXCEEDED')
        twice = wire_output(candidates, [3, 3])
        self.assertEqual(reduce_with(OCTOBER_7_MODEL, Claude(twice), candidates)[0]['reason'], 'UNKNOWN_OR_DUPLICATE_CANDIDATE')

    def test_no_wire_value_binds_one_candidate_to_anothers_evidence(self):
        candidates, _ = packed()
        ids = [set(reference_ids(c)) for c in candidates]
        self.assertEqual(sum(len(x) for x in ids), len(set().union(*ids)), 'evidence ids are unique to their candidate')
        widest = max(len(x) for x in ids)
        for key in (0, 17, MAX_INTAKE - 1):
            for index in range(-1, widest + 1):
                answer = {'schema_version': SCHEMA_VERSION, 'candidates': [{**wire_pick(candidates, key, 1), 'conflicting_refs': [index]}],
                          'limitations': ['x']}
                parsed, _ = parse_reduction(json.dumps(answer), candidates)
                if parsed:
                    pick = parsed['candidates'][0]
                    self.assertTrue({*pick['supporting_refs'], *pick['conflicting_refs'], *pick['weak_refs']} <= ids[key])
                    self.assertEqual(pick['instrument_id'], candidates[key]['instrument']['instrument_id'])

    def test_candidate_key_is_the_request_local_position_and_nothing_else(self):
        candidates, _ = packed(8)
        first, second = packet_candidates(candidates), packet_candidates(candidates)
        self.assertEqual(first, second)
        self.assertEqual([c['candidate_key'] for c in first], list(range(8)))
        self.assertTrue(all('candidate_key' not in c for c in candidates), 'the canonical candidates never carry the key')
        # The same key in a different request names that request's candidate at that position.
        reordered = list(reversed(candidates))
        parsed, _ = parse_reduction(json.dumps(wire_output(reordered, [2])), reordered)
        self.assertEqual(parsed['candidates'][0]['instrument_id'], reordered[2]['instrument']['instrument_id'])
        self.assertNotEqual(reordered[2]['instrument']['instrument_id'], candidates[2]['instrument']['instrument_id'])


class LineageTests(unittest.TestCase):
    def test_wire_version_schema_hash_and_prompt_are_recorded_and_part_of_cache_identity(self):
        candidates, _ = packed(3)
        transport = Claude(wire_output(candidates, [0]))
        result, reducer = reduce_with(OCTOBER_7_MODEL, transport, candidates)
        prompt = PromptRegistry().get_by_id(PROMPT_ID)
        from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict
        self.assertEqual(result['wire_schema_version'], WIRE_SCHEMA_VERSION)
        self.assertEqual(result['output_schema_hash'], input_hash_from_dict(output_schema(candidates)))
        self.assertEqual((result['prompt_id'], result['prompt_version'], result['prompt_hash']), (PROMPT_ID, '3.0.0', prompt.content_hash))
        identity = reducer.estimate({}, candidates, NEWS_ISO)['input_hash']
        self.assertEqual(identity, result['input_hash'])
        with patch.object(candidate_reduction, 'WIRE_SCHEMA_VERSION', 'ai-screener-wire/next'):
            self.assertNotEqual(reducer.estimate({}, candidates, NEWS_ISO)['input_hash'], identity)
        with patch.object(candidate_reduction, 'PROMPT_ID', 'screener.ai_candidate_reduction.v2'):
            self.assertNotEqual(reducer.estimate({}, candidates, NEWS_ISO)['input_hash'], identity)
        with patch.object(candidate_reduction, 'MAX_SELECTED', 4):
            self.assertNotEqual(reducer.estimate({}, candidates, NEWS_ISO)['input_hash'], identity)
        other = CandidateReducer(provider=AnthropicSynthesisProvider(api_key='controlled', model='claude-opus-5-5', poster=transport), clock=lambda: CLOCK)
        self.assertNotEqual(other.estimate({}, candidates, NEWS_ISO)['input_hash'], identity)


class EnginePickerTruthTests(unittest.TestCase):
    def test_engine_options_state_ai_screener_compatibility_for_every_offered_claude_model(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            options = {o['id']: o for o in engine_options({'ANTHROPIC_API_KEY': 'controlled'}.get, Path(directory))}
            rows = options['anthropic']['model_contracts']
            self.assertEqual([r['model'] for r in rows], SELECTABLE)
            self.assertTrue(all(r['ai_screener_compatible'] and r['reason'] is None for r in rows))
            self.assertEqual({r['model']: r['context_window'] for r in rows},
                             {'claude-sonnet-5-5': 1_000_000, OCTOBER_7_MODEL: 200_000, 'claude-opus-5-5': 1_000_000})
            self.assertIsNone(options['openai']['model_contracts'])
            env = {'ANTHROPIC_API_KEY': 'controlled', 'IMP_SYNTHESIS_ANTHROPIC_MODEL': 'claude-fable-5-1'}
            configured = {o['id']: o for o in engine_options(env.get, Path(directory))}['anthropic']
            self.assertEqual(configured['default_model'], 'claude-fable-5-1')
            self.assertEqual(configured['model_contracts'][0],
                             {'model': 'claude-fable-5-1', 'context_window': None, 'ai_screener_compatible': False,
                              'reason': UNSUPPORTED, 'required_contract': 'STRICT_TOOL_SCHEMA',
                              'unsupported_capability': 'MODEL_NOT_IN_CAPABILITY_TABLE'})


class HistoricalFailureReplayTests(unittest.TestCase):
    """One focused reproduction per blocker met on the road to this contract."""

    @classmethod
    def setUpClass(cls):
        cls.candidates, _ = packed()
        cls.schema_text = json.dumps(output_schema(cls.candidates))

    def test_missing_evidence_mismatch_cannot_arise_from_the_wire(self):
        # The model once had to restate each candidate's missing list and got it wrong. It no longer states it.
        self.assertNotIn('missing_capabilities', self.schema_text)
        result, _ = reduce_with(OCTOBER_7_MODEL, Claude(wire_output(self.candidates, [0, 1])), self.candidates)
        self.assertEqual(result['reason'], None)
        restated = {**wire_pick(self.candidates, 0, 1), 'missing_capabilities': ['NEWS']}
        answer = {'schema_version': SCHEMA_VERSION, 'candidates': [restated], 'limitations': ['x']}
        self.assertEqual(parse_reduction(json.dumps(answer), self.candidates)[1], 'SCHEMA_INVALID')
        # The canonical check itself still stands behind the wire.
        parsed, _ = parse_reduction(json.dumps(wire_output(self.candidates, [0])), self.candidates)
        wrong = {**parsed['candidates'][0], 'missing_capabilities': []}
        self.assertEqual(parse_reduction(json.dumps({'schema_version': SCHEMA_VERSION, 'candidates': [wrong], 'limitations': ['x']}),
                                         self.candidates)[1], 'MISSING_EVIDENCE_MISMATCH')

    def test_no_constant_of_any_kind_is_sent_to_the_strict_grammar(self):
        self.assertNotIn('"const"', self.schema_text)

    def test_grammar_stays_small_and_flat_at_full_intake(self):
        self.assertLess(len(self.schema_text), 3000)
        for branching in ('anyOf', 'oneOf', 'allOf', '$ref'):
            self.assertNotIn(branching, self.schema_text)
        enums = re.findall(r'"enum": \[([^\]]*)\]', self.schema_text)
        self.assertLessEqual(max(len(e.split(',')) for e in enums), MAX_INTAKE)

    def test_prompt_names_no_field_the_schema_removed(self):
        template = PromptRegistry().get_by_id(PROMPT_ID).template
        for removed in ('weak_refs', 'missing_capabilities', 'instrument_id'):
            self.assertNotIn(removed, template)
            self.assertNotIn(removed, self.schema_text)

    def test_cross_instrument_reference_has_no_wire_representation(self):
        # A is asked to cite B's news: B's evidence has no index inside A, so no value on the wire can name it.
        a, b = 0, 1
        b_news = next(e['evidence_id'] for e in self.candidates[b]['reference_evidence'] if e['capability'] == 'NEWS')
        self.assertNotIn(b_news, reference_ids(self.candidates[a]))
        for index in range(len(reference_ids(self.candidates[a])) + 3):
            answer = {'schema_version': SCHEMA_VERSION, 'candidates': [{**wire_pick(self.candidates, a, 1), 'conflicting_refs': [index]}],
                      'limitations': ['x']}
            parsed, _ = parse_reduction(json.dumps(answer), self.candidates)
            if parsed:
                self.assertNotIn(b_news, parsed['candidates'][0]['conflicting_refs'])

    def test_unsupported_request_parameters_are_not_sent_to_the_default_model(self):
        transport = Claude(wire_output(self.candidates, [0]))
        result, _ = reduce_with(DEFAULT_MODEL, transport, self.candidates)
        body = transport.requests[0][1]
        self.assertEqual(result['state'], 'CURRENT')
        self.assertNotIn('temperature', body)
        self.assertNotEqual(body['tool_choice']['type'], 'tool')


if __name__ == '__main__':
    unittest.main()
