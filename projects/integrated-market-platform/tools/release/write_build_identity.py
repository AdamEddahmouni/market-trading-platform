"""Write or verify BUILD-IDENTITY.json at an application root (AUD-037, AUD-040). Owner-run release step.

  write_build_identity.py write  --target <application folder> --revision <40-hex commit> --release <name>
  write_build_identity.py verify --target <application folder>

The serving tree has no git metadata, so the runtime (src/market_platform_foundation/build_identity.py) reads the
source revision from this file. ``write`` records the revision the release was built from (the RC manifest's
``commit``), a build id, the time and a SHA-256 over every ``src/**/*.py`` and ``tools/**/*.py`` file of the target.
``verify`` recomputes that digest read-only and reports whether the tree still matches. Neither guesses a revision:
``--revision`` must be a full commit hash supplied by the release, and an existing file is replaced only with
``--replace``. tools/release_candidate/apply_release.py calls ``write`` after a successful apply.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'imp.build-identity/1'
FILENAME = 'BUILD-IDENTITY.json'
MANIFEST_GLOBS = ('src/**/*.py', 'tools/**/*.py')
REVISION = re.compile(r'[0-9a-f]{40}')


def manifest_digest(target):
    """SHA-256 over sorted (relative path, file SHA-256) lines of the release's Python sources."""
    lines = []
    for pattern in MANIFEST_GLOBS:
        for path in target.glob(pattern):
            if path.is_file() and '__pycache__' not in path.parts:
                lines.append(f"{path.relative_to(target).as_posix()} {hashlib.sha256(path.read_bytes()).hexdigest()}")
    lines.sort()
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest(), len(lines)


def build_identity(target, *, revision, release, now=None):
    if not REVISION.fullmatch(revision or ''):
        raise ValueError('REVISION_MUST_BE_A_FULL_40_HEX_COMMIT')
    if not release:
        raise ValueError('RELEASE_NAME_REQUIRED')
    built_at = (now or datetime.now(timezone.utc)).isoformat().replace('+00:00', 'Z')
    digest, count = manifest_digest(target)
    build_id = 'BUILD-' + hashlib.sha256(f'{release}|{revision}|{digest}'.encode('utf-8')).hexdigest()[:24]
    return dict(schema=SCHEMA, source_revision=revision, release=release, build_id=build_id, built_at=built_at,
                manifest_sha256=digest, manifest_files=count, manifest_globs=list(MANIFEST_GLOBS))


def write(target, *, revision, release, replace=False, now=None):
    path = target / FILENAME
    if path.exists() and not replace:
        raise FileExistsError('BUILD_IDENTITY_EXISTS_USE_REPLACE')
    body = build_identity(target, revision=revision, release=release, now=now)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(body, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
    return body


def verify(target):
    path = target / FILENAME
    if not path.is_file():
        return dict(status='MISSING', path=str(path))
    body = json.loads(path.read_text(encoding='utf-8'))
    digest, count = manifest_digest(target)
    matches = digest == body.get('manifest_sha256')
    return dict(status='MATCH' if matches else 'TREE_CHANGED_SINCE_BUILD', path=str(path),
                source_revision=body.get('source_revision'), build_id=body.get('build_id'),
                recorded_files=body.get('manifest_files'), current_files=count)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('write', 'verify'))
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--revision')
    parser.add_argument('--release')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args(argv)
    target = args.target.resolve()
    if args.command == 'verify':
        result = verify(target)
        print(json.dumps(result, indent=1))
        return 0 if result['status'] == 'MATCH' else 1
    print(json.dumps(write(target, revision=args.revision, release=args.release, replace=args.replace), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
