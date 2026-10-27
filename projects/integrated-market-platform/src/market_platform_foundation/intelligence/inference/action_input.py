"""Lossless Action Decision transport and bounded provider diagnostics.

The canonical candidate, input hash, policy, validators and persisted snapshot
retain their original evidence. Only the local model input uses column rows.
"""
from __future__ import annotations

import copy
import re
from .evidence_compaction import compact, reconstruct as unpack, verify

VERSION = 'action-evidence-columns/1.0.0'

SAFE_PROVIDER_REASONS = frozenset({
    'LOCAL_CONTEXT_EXCEEDED', 'LOCAL_CONTEXT_PREFLIGHT_FAILED', 'LOCAL_CONTEXT_UNAVAILABLE',
    'LOCAL_ENDPOINT_NOT_LOOPBACK', 'LOCAL_MODEL_TIMEOUT', 'LOCAL_MODEL_UNAVAILABLE',
    'LOCAL_MODEL_RESPONSE_MALFORMED', 'LOCAL_OUTPUT_LIMIT_REACHED', 'LOCAL_TEMPLATE_UNAVAILABLE',
    'LOCAL_TOKENIZER_UNAVAILABLE', 'LOCAL_QUALIFICATION_REQUIRES_OWNED_PINNED_RUNTIME',
    'LOCAL_RESOURCE_MEMORY_LIMIT', 'LOCAL_RESOURCE_INSUFFICIENT_MEMORY', 'LOCAL_RESOURCE_COMMIT_LIMIT',
    'LOCAL_RESOURCE_COMMIT_HEADROOM', 'LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE',
    'LOCAL_RESOURCE_PREDICTED_PROCESS_LIMIT', 'LOCAL_RESOURCE_PREDICTED_VRAM_LIMIT', 'LOCAL_RESOURCE_PREDICTED_UNSAFE',
    'LOCAL_RUNTIME_PROFILE_INVALID', 'LOCAL_RUNTIME_PROFILE_CONTEXT_LIMIT', 'LOCAL_RUNTIME_PROFILE_MISMATCH',
    'LOCAL_PINNED_RUNTIME_PLATFORM_UNSUPPORTED', 'LOCAL_RUNTIME_FILE_SET_MISMATCH',
    'LOCAL_RUNTIME_ARCHIVE_CHECKSUM_FAILED', 'LOCAL_RUNTIME_CHECKSUM_FAILED',
    'LOCAL_ARTIFACT_CHANGED_DURING_VERIFICATION', 'LOCAL_ARTIFACT_VERIFICATION_UNAVAILABLE',
    'LOCAL_RUNTIME_NOT_FOUND', 'LOCAL_MODEL_FILE_NOT_FOUND', 'LOCAL_MODEL_PORT_IN_USE',
    'LOCAL_RUNTIME_ALREADY_OWNED_OR_INTERRUPTED', 'LOCAL_RUNTIME_OWNERSHIP_UNAVAILABLE',
    'LOCAL_RUNTIME_START_TIMEOUT', 'LOCAL_RUNTIME_START_FAILED', 'LOCAL_RUNTIME_EXITED',
    'LOCAL_INFERENCE_QUEUE_FULL', 'LOCAL_INFERENCE_BUSY',
    'PINNED_LOCAL_MODEL_REQUIRED', 'STOPPED_BY_OPERATOR',
})



def encode(data):
    candidate=copy.deepcopy(data['candidate'])
    aliases={}
    for alias,key in (('blocked_evidence','blocked'),('missing_evidence','missing'),('weak_evidence','weak')):
        if alias in candidate and key in candidate and candidate[alias]==candidate[key]:
            aliases[alias]=key
            del candidate[alias]
    manifest=dict(scope={},decision_cutoff=data['decision_cutoff'],candidates=[candidate])
    packed=compact(manifest)
    if not verify(manifest,packed):
        raise ValueError('ACTION_COMPACTION_NOT_EQUIVALENT')
    result={k:copy.deepcopy(v) for k,v in data.items() if k!='candidate'}
    result.update(encoding=VERSION,candidate_columns=packed,candidate_aliases=aliases,
        encoding_instructions='candidate_columns.rows[0] is the candidate: identity row, current-market rows, reference rows. '
            'Each row is [values, absent-column-indices]. Use columns for identity, evidence_columns for evidence. '
            'candidate_aliases names exact duplicate candidate fields. All evidence and conditions remain authoritative DATA.')
    if reconstruct(result)!=data:
        raise ValueError('ACTION_COMPACTION_NOT_EQUIVALENT')
    return result


def reconstruct(packed):
    if packed['encoding']!=VERSION:
        raise ValueError('ACTION_ENCODING_UNSUPPORTED')
    candidate=unpack(packed['candidate_columns'])['candidates'][0]
    for alias,key in packed['candidate_aliases'].items():
        candidate[alias]=copy.deepcopy(candidate[key])
    result={k:copy.deepcopy(v) for k,v in packed.items()
        if k not in ('encoding','candidate_columns','candidate_aliases','encoding_instructions')}
    result['candidate']=candidate
    return result


def provider_diagnostics(response):
    # Never persist arbitrary error text, HTTP bodies, resource objects or prompts.
    raw=response.diagnostics if isinstance(response.diagnostics,dict) else {}
    context=raw.get('context') if isinstance(raw.get('context'),dict) else {}
    safe_context={key:value for key,value in context.items()
        if key in ('input_tokens','output_allowance','output_floor','configured_max_tokens','context_window')
        and type(value) is int and -(10**9)<=value<=10**9}
    code=getattr(response.error_code,'value',None)
    reason=response.error_message
    reason=reason if isinstance(reason,str) and (reason in SAFE_PROVIDER_REASONS or re.fullmatch(r'LOCAL_MODEL_HTTP_[1-5][0-9]{2}',reason)) else None
    result=dict(error_code=code,error_message=reason,
        inference_dispatched=response.inference_dispatched if type(response.inference_dispatched) is bool else None,
        diagnostics=dict(context=safe_context))
    if code:
        result.update(failure_category='CONTEXT_BUDGET_REFUSAL' if reason=='LOCAL_CONTEXT_EXCEEDED' else 'PROVIDER_FAILURE',
            failure_stage='CONTEXT_PREFLIGHT' if reason in ('LOCAL_CONTEXT_EXCEEDED','LOCAL_CONTEXT_PREFLIGHT_FAILED')
                else 'GENERATION' if result['inference_dispatched'] else 'PROVIDER_ADMISSION')
    return result
