"""Verify, apply or roll back the release delta on an application tree. Owner-run; nothing here runs by itself.

  apply_release.py verify   --target <application folder>
  apply_release.py apply    --target <application folder> --preimage-dir <new folder>
  apply_release.py rollback --target <application folder> --preimage-dir <the folder apply wrote>

verify reads only. apply first checks every pre-image and every preserved file against RC_MANIFEST.json, refuses
while a Python process is running from the target, saves each file it will replace, then copies the delta and
verifies the result. When the collector's RELEASE_MANIFEST.json lists a replaced file, apply updates that hash
only after the installed bytes match the release and the manifest still named the pre-image. It does not add
files the collector was not already checking. rollback restores the saved manifest bytes with the saved sources.
Neither touches a database: source rollback alone does not undo a schema
migration (see DEPLOYMENT_DECISION_PACKAGE.md). The same functions are exercised by rehearsal/deploy_rehearsal.py.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RC = Path(os.environ.get('RC_DIR') or Path(__file__).resolve().parent)  # RC_DIR: a package built into another folder
RECORD = 'APPLIED.json'
# The identity writer ships in tools/release, or next to this file in a package built into another folder.
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'release')]
try:
    import write_build_identity  # noqa: E402
except ImportError:  # an older package: the apply still works and its record says no identity was written
    write_build_identity = None
IDENTITY = 'BUILD-IDENTITY.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def discover_collector_manifest(target):
    """The collector's integrity file lives beside the application, not inside it.

    An explicit ``IMP_COLLECTOR_RELEASE_MANIFEST`` wins. Otherwise the portable
    layout ``<root>/collector/RELEASE_MANIFEST.json`` is used when that file exists.
    A tree with no collector manifest is a valid rehearsal target.
    """
    override = os.environ.get('IMP_COLLECTOR_RELEASE_MANIFEST', '')
    if override:
        return Path(override)
    candidate = target.parent.parent / 'collector' / 'RELEASE_MANIFEST.json'
    return candidate if candidate.is_file() else None


def load_collector_manifest(path):
    body = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(body, dict) or not isinstance(body.get('files'), dict) or not body['files']:
        raise RuntimeError('COLLECTOR_MANIFEST_UNREADABLE')
    record = body.get('release_applications', [])
    if not isinstance(record, list):
        raise RuntimeError('COLLECTOR_MANIFEST_RECORD_INVALID')
    return body


def collector_problems(target, manifest, manifest_path, entries=None):
    """A listed file may be replaced only when the manifest still names its current bytes.

    Files the collector does not list are its own concern and are not added here.
    """
    if manifest_path is None or not Path(manifest_path).is_file():
        return []
    try:
        files = load_collector_manifest(manifest_path)['files']
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
        return ['COLLECTOR_MANIFEST_UNREADABLE']
    problems = []
    for item in manifest['files'] if entries is None else entries:
        rel = item['path'].replace('\\', '/')
        if rel not in files:
            continue
        if files[rel] != sha(target / item['path']):
            problems.append(f"COLLECTOR_MANIFEST_DIVERGED {rel}")
    return problems


def load_manifest(rc=RC):
    return json.loads((rc / 'RC_MANIFEST.json').read_text(encoding='utf-8'))


def verify(target, manifest, collector_manifest=None):
    """Problems that must stop an apply: a changed pre-image, a changed preserved file, an unresolved conflict."""
    problems = [f"CONFLICT {item['path']}: {item['conflict']}" for item in manifest['conflicts']]
    for item in manifest['files']:
        if sha(target / item['path']) != item['serving_preimage_sha256']:
            problems.append(f"PREIMAGE_CHANGED {item['path']}")
    for item in manifest['preserve']:
        if sha(target / item['path']) != item['sha256']:
            problems.append(f"PRESERVED_FILE_CHANGED {item['path']}")
    path = discover_collector_manifest(target) if collector_manifest is None else collector_manifest
    problems.extend(collector_problems(target, manifest, path))
    return problems


def applied_state(target, manifest):
    return [item['path'] for item in manifest['files'] if sha(target / item['path']) != item['sha256']]


def running_from(target):
    """Python processes whose command line names the target tree (the serving backend, control service or a tool)."""
    inventory = subprocess.run(['powershell', '-NoProfile', '-Command',
                              "$ErrorActionPreference='Stop'; Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                              "ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"],
                             capture_output=True, text=True)
    listing = inventory.stdout.splitlines()
    if (inventory.returncode or inventory.stderr.strip()
            or any(not line.partition('|')[0].isdigit() or not line.partition('|')[1]
                   or not line.partition('|')[2].strip() for line in listing)):
        raise RuntimeError('PROCESS_INVENTORY_UNAVAILABLE')
    needle, own = str(target).lower(), str(os.getpid())  # this tool's own command line names the target
    return [line.partition('|')[2].strip()[:160] for line in listing
            if line.partition('|')[0] != own and needle.replace('/', '\\') in line.lower().replace('/', '\\')]


def _sync_collector_manifest(target, preimage_dir, manifest, manifest_path, record):
    """Point listed hashes at the bytes just installed, and keep every other entry.

    The previous manifest is saved byte for byte so rollback restores the same
    source/manifest pair. A file this release does not list is left alone, and a
    hash that already matches is not rewritten.
    """
    body = load_collector_manifest(manifest_path)
    updates = []
    for item in manifest['files']:
        rel = item['path'].replace('\\', '/')
        if rel not in body['files']:
            continue
        installed = sha(target / item['path'])
        if installed != item['sha256']:
            raise RuntimeError(f'COLLECTOR_MANIFEST_INSTALL_MISMATCH {rel}')
        if body['files'][rel] == installed:
            continue
        body['files'][rel] = installed
        updates.append(rel)
    saved = preimage_dir / 'collector' / 'RELEASE_MANIFEST.json'
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, saved)
    record['collector_manifest'] = {'path': str(manifest_path), 'updated': updates, 'preimage': str(saved)}
    (preimage_dir / RECORD).write_text(json.dumps(record, indent=1), encoding='utf-8')
    if not updates:
        return
    body.setdefault('release_applications', []).append({
        'at': datetime.now(timezone.utc).isoformat(),
        'release': manifest['release'],
        'commit': manifest['commit'],
        'files': updates,
    })
    temporary = manifest_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(body, indent=2) + '\n', encoding='utf-8')
    temporary.replace(manifest_path)


def apply(target, preimage_dir, manifest, *, rc=RC, entries=None, collector_manifest=None):
    """Save what will be replaced, then copy. ``entries`` limits the copy (the rehearsal's interrupted apply)."""
    entries = manifest['files'] if entries is None else entries
    manifest_path = discover_collector_manifest(target) if collector_manifest is None else collector_manifest
    diverged = collector_problems(target, manifest, manifest_path, entries)
    if diverged:
        raise RuntimeError(diverged[0])
    preimage_dir.mkdir(parents=True, exist_ok=False)
    record = {'release': manifest['release'], 'commit': manifest['commit'], 'target': str(target),
              'started_utc': datetime.now(timezone.utc).isoformat(), 'replaced': [], 'added': [], 'complete': False}
    (preimage_dir / RECORD).write_text(json.dumps(record, indent=1), encoding='utf-8')
    for item in entries:
        destination = target / item['path']
        if destination.exists():
            saved = preimage_dir / 'files' / item['path']
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
            record['replaced'].append(item['path'])
        else:
            record['added'].append(item['path'])
        (preimage_dir / RECORD).write_text(json.dumps(record, indent=1), encoding='utf-8')  # durable before each write to the tree
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rc / 'delta' / item['path'], destination)
    record['complete'] = len(entries) == len(manifest['files'])
    if record['complete'] and write_build_identity is None:
        record['identity'] = None
        record['identity_skipped'] = 'WRITE_BUILD_IDENTITY_NOT_SHIPPED'
    elif record['complete']:
        # The serving tree has no git metadata: name the revision this release was built from (AUD-037/040). The
        # previous identity is saved like any replaced file, so rollback restores it.
        identity = target / IDENTITY
        if identity.exists():
            saved = preimage_dir / 'files' / IDENTITY
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(identity, saved)
        record['identity'] = {'preexisting': identity.exists()}
        (preimage_dir / RECORD).write_text(json.dumps(record, indent=1), encoding='utf-8')
        record['identity'].update(write_build_identity.write(target, revision=manifest['commit'],
                                                             release=manifest['release'], replace=True))
    if record['complete'] and manifest_path is not None and Path(manifest_path).is_file():
        _sync_collector_manifest(target, preimage_dir, manifest, Path(manifest_path), record)
    record['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (preimage_dir / RECORD).write_text(json.dumps(record, indent=1), encoding='utf-8')
    return record


def rollback(target, preimage_dir, manifest):
    """Back to the tree as it was before apply. An added file that no longer equals the delta is left and reported."""
    record = json.loads((preimage_dir / RECORD).read_text(encoding='utf-8'))
    by_path = {item['path']: item for item in manifest['files']}
    kept = []
    for path in record['replaced']:
        shutil.copy2(preimage_dir / 'files' / path, target / path)
    for path in record['added']:
        destination = target / path
        if not destination.exists():
            continue
        if sha(destination) != by_path[path]['sha256']:
            kept.append(path)
            continue
        destination.unlink()
        parent = destination.parent
        while parent != target and not any(parent.iterdir()):  # folders the release created
            parent.rmdir()
            parent = parent.parent
    collector = record.get('collector_manifest')
    if collector is not None:
        shutil.copy2(preimage_dir / 'collector' / 'RELEASE_MANIFEST.json', collector['path'])
    identity = record.get('identity')
    if identity is not None:
        if identity.get('preexisting'):
            shutil.copy2(preimage_dir / 'files' / IDENTITY, target / IDENTITY)
        elif (target / IDENTITY).exists():
            (target / IDENTITY).unlink()
    collector_path = (record.get('collector_manifest') or {}).get('path')
    remaining = verify(target, manifest, collector_path)
    return {'restored': len(record['replaced']), 'removed': len(record['added']) - len(kept), 'added_files_left_because_changed': kept,
            'tree_matches_pre_release_manifest': not remaining and not kept, 'problems': remaining}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('verify', 'apply', 'rollback'))
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--preimage-dir', type=Path)
    parser.add_argument('--collector-manifest', type=Path)
    args = parser.parse_args()
    target, manifest = args.target.resolve(), load_manifest()
    if not (target / 'tools/ui1/run_ui_api.py').is_file():
        raise SystemExit('TARGET_IS_NOT_AN_APPLICATION_TREE')
    collector_manifest = args.collector_manifest.resolve() if args.collector_manifest else None
    if args.command == 'verify':
        problems = verify(target, manifest, collector_manifest)
        not_applied = applied_state(target, manifest)
        print(json.dumps({'release': manifest['release'], 'commit': manifest['commit'], 'target': str(target),
                          'delta_files': len(manifest['files']), 'ready_to_apply': not problems,
                          'already_applied': not not_applied, 'problems': problems[:20], 'problem_count': len(problems),
                          'python_processes_running_from_target': running_from(target)}, indent=1))
        raise SystemExit(0 if not problems or not not_applied else 1)
    if args.preimage_dir is None:
        raise SystemExit('PREIMAGE_DIR_REQUIRED')
    preimage_dir = args.preimage_dir.resolve()
    running = running_from(target)
    if running:
        print(json.dumps({'refused': 'APPLICATION_RUNNING_FROM_TARGET', 'processes': running}, indent=1))
        raise SystemExit(2)
    if args.command == 'apply':
        problems = verify(target, manifest, collector_manifest)
        if problems:
            print(json.dumps({'refused': 'TARGET_DOES_NOT_MATCH_THE_REVIEWED_PRE_IMAGES', 'problems': problems[:20]}, indent=1))
            raise SystemExit(1)
        record = apply(target, preimage_dir, manifest, collector_manifest=collector_manifest)
        wrong = applied_state(target, manifest)
        preserved = [item['path'] for item in manifest['preserve'] if sha(target / item['path']) != item['sha256']]
        print(json.dumps({'applied': record['complete'] and not wrong and not preserved, 'replaced': len(record['replaced']),
                          'added': len(record['added']), 'files_not_equal_to_release': wrong, 'preserved_files_changed': preserved,
                          'preimage_dir': str(preimage_dir)}, indent=1))
        raise SystemExit(0 if record['complete'] and not wrong and not preserved else 1)
    outcome = rollback(target, preimage_dir, manifest)
    print(json.dumps(outcome, indent=1))
    raise SystemExit(0 if outcome['tree_matches_pre_release_manifest'] else 1)


if __name__ == '__main__':
    main()
