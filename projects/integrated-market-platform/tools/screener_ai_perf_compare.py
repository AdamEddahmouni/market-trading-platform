"""Compare attributable Screener profiles; incompatible records carry raw times only."""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

COMPARABLE = 'COMPARABLE'
INCOMPATIBLE_WORKLOAD = 'INCOMPATIBLE_WORKLOAD'
INCOMPATIBLE_ENVIRONMENT = 'INCOMPATIBLE_ENVIRONMENT'
INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'
NOISE_FLOOR_MS = 0.25
_FIXTURE_KEYS = ('identity', 'provider_rows', 'admitted_rows', 'admitted_target',
                 'requested_universe', 'page_limit', 'quick_mode')
_ENVIRONMENT_KEYS = ('python', 'implementation', 'platform', 'processor', 'cpu_count',
                     'machine_identity', 'physical_memory_bytes')
_PARITY_KEYS = ('ordered_match_digest', 'ordered_matched', 'filtered_by',
                'full_universe_values_digest', 'api_payload_digest', 'observations_digest')
_METHOD_KEYS = ('tool_sha256', 'clock', 'warmup', 'gc_enabled', 'memory', 'cache',
                'measurement', 'excluded', 'source_cleanliness_scope')


def _verdict(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, list[str]]:
    missing, workload, environment = [], [], []
    for label, record in (('before', before), ('after', after)):
        source = record.get('source') or {}
        if not re.fullmatch(r'[0-9a-f]{40}', str(source.get('sha', ''))):
            missing.append(f'{label}: exact source SHA unavailable')
        if source.get('dirty') is not False:
            missing.append(f'{label}: source is dirty or its status is unknown')
    for group, keys, errors in (
        (None, ('profile_version', 'methodology'), workload),
        ('fixture', _FIXTURE_KEYS, workload),
        ('parity', _PARITY_KEYS, workload),
        ('methodology', _METHOD_KEYS, workload),
        ('environment', _ENVIRONMENT_KEYS, environment),
    ):
        old = before if group is None else before.get(group) or {}
        new = after if group is None else after.get(group) or {}
        for key in keys:
            name = f'{group}.{key}' if group else key
            if key not in old or key not in new or old[key] is None or new[key] is None or old[key] == '' or new[key] == '':
                missing.append(f'{name}: required identity missing')
            elif old[key] != new[key]:
                errors.append(f'{name}: identities differ')
    if missing:
        return INSUFFICIENT_EVIDENCE, missing + workload + environment
    if environment:
        return INCOMPATIBLE_ENVIRONMENT, environment + workload
    if workload:
        return INCOMPATIBLE_WORKLOAD, workload
    return COMPARABLE, []


def _finite_positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _valid_stage(stage: dict[str, Any]) -> bool:
    repeat, warmup, samples = stage.get('repeat'), stage.get('warmup'), stage.get('samples_ms')
    if type(repeat) is not int or repeat < 3 or type(warmup) is not int or warmup < 1:
        return False
    if not isinstance(samples, list) or len(samples) != repeat or not all(_finite_positive(value) for value in samples):
        return False
    ordered = sorted(samples)
    expected = {'median_ms': statistics.median(ordered), 'mean_ms': statistics.fmean(ordered),
                'min_ms': ordered[0], 'max_ms': ordered[-1],
                'p95_ms': ordered[min(repeat - 1, int(repeat * .95))],
                'stddev_ms': statistics.stdev(ordered)}
    for key, value in expected.items():
        actual = stage.get(key)
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(actual) or actual < 0:
            return False
        if key != 'stddev_ms' and actual == 0:
            return False
        if not math.isclose(actual, value, rel_tol=1e-6, abs_tol=.00011):
            return False
    return True


def _inventory(record: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    stages = record.get('stages')
    if not isinstance(stages, list) or not stages:
        return None
    result = {}
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get('stage'), str) or not stage['stage'] or stage['stage'] in result:
            return None
        result[stage['stage']] = stage
    return result


def compare(before: dict[str, Any], after: dict[str, Any], *, threshold: float) -> dict[str, Any]:
    if not _finite_positive(threshold) or threshold <= 1:
        raise ValueError('threshold must be finite and greater than one')
    status, reasons = _verdict(before, after)
    old_stages, new_stages = _inventory(before), _inventory(after)
    if old_stages is None or new_stages is None:
        status = INSUFFICIENT_EVIDENCE
        reasons.append('stage inventory missing, empty, malformed, or duplicated')
    old_stages, new_stages = old_stages or {}, new_stages or {}
    rows = []
    for name in sorted(set(old_stages) | set(new_stages)):
        old, new = old_stages.get(name), new_stages.get(name)
        row = {'stage': name, 'verdict': status}
        if old is None or new is None:
            row.update(verdict=INSUFFICIENT_EVIDENCE, reason='stage missing on one side')
            rows.append(row)
            continue
        row.update(before_median_ms=old.get('median_ms'), after_median_ms=new.get('median_ms'),
                   before_p95_ms=old.get('p95_ms'), after_p95_ms=new.get('p95_ms'))
        if not all(_valid_stage(item) for item in (old, new)):
            row.update(verdict=INSUFFICIENT_EVIDENCE, reason='samples, variance, summary, warmup, or repetitions invalid')
        elif old.get('repeat') != new.get('repeat') or old.get('warmup') != new.get('warmup'):
            row.update(verdict=INSUFFICIENT_EVIDENCE, reason='repetition counts missing or different')
        elif old.get('value') != new.get('value'):
            row.update(verdict=INCOMPATIBLE_WORKLOAD, reason='stage result values differ')
        elif status == COMPARABLE:
            old_ms, new_ms = old['median_ms'], new['median_ms']
            ratio, delta = new_ms / old_ms, new_ms - old_ms
            # A conservative two-standard-error floor supplements the absolute
            # floor. Raw distributions are retained for assessment across runs.
            uncertainty = 2 * math.sqrt(sum((item['stddev_ms'] ** 2) / item['repeat'] for item in (old, new)))
            noise = max(NOISE_FLOOR_MS, uncertainty)
            within_noise = abs(delta) < noise
            row.update(delta_ms=round(delta, 4), ratio=round(ratio, 4),
                       change_pct=round((ratio - 1) * 100, 1), within_noise_floor=within_noise,
                       effective_noise_floor_ms=noise,
                       regression=not within_noise and ratio > threshold,
                       improvement=not within_noise and ratio < 1 / threshold)
            if not within_noise:
                row['speedup'] = round(1 / ratio, 3)
        else:
            row['reason'] = 'ratio withheld: identity or provenance does not support comparison'
        rows.append(row)
    if status == COMPARABLE and any(row['verdict'] != COMPARABLE for row in rows):
        status = INSUFFICIENT_EVIDENCE
        reasons.append('one or more stages lack compatible measurements')
    return {
        'report_version': 'screener-ai-perf-compare/2.0.0', 'verdict': status, 'verdict_reasons': reasons,
        'before': {'sha': (before.get('source') or {}).get('sha'), 'generated_at': before.get('generated_at'), 'fixture': before.get('fixture')},
        'after': {'sha': (after.get('source') or {}).get('sha'), 'generated_at': after.get('generated_at'), 'fixture': after.get('fixture')},
        'threshold_ratio': threshold, 'noise_floor_ms': NOISE_FLOOR_MS, 'stage_count': len(rows),
        'improved_stages': sum(bool(row.get('improvement')) for row in rows),
        'regressed_stages': [row['stage'] for row in rows if row.get('regression')],
        'comparison_policy': {
            COMPARABLE: 'exact clean source identities; same fixture values, environment, methodology, and repetitions',
            INCOMPATIBLE_WORKLOAD: 'fixture, results, or methodology differ; no ratio',
            INCOMPATIBLE_ENVIRONMENT: 'machine, operating system, memory, or interpreter differ; no ratio',
            INSUFFICIENT_EVIDENCE: 'missing identity, dirty source, invalid duration, or incomplete measurements',
        }, 'stages': rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--threshold', type=float, default=1.15)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = compare(json.loads(args.before.read_text(encoding='utf-8')),
                     json.loads(args.after.read_text(encoding='utf-8')), threshold=args.threshold)
    print('verdict:', report['verdict'])
    for reason in report['verdict_reasons']:
        print(' -', reason)
    for row in report['stages']:
        print(row['stage'], row.get('before_median_ms'), '->', row.get('after_median_ms'),
              'ms', 'noise' if row.get('within_noise_floor') else row.get('speedup', row['verdict']))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return 0 if report['verdict'] == COMPARABLE and not report['regressed_stages'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
