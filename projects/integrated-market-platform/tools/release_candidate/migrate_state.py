"""Migrate one IMP local-state database with the applied release's own connection authority, and prove what changed.

  migrate_state.py --application <application folder with the release applied> --database <state folder>\\imp-state.sqlite3

Owner-run, after a verified backup. The migration itself is the release code's (the same one a first start of the
application would run); this tool only makes it an explicit step with a before/after comparison: same file, schema
11 -> 13, integrity and foreign keys ok, every table that existed before logically identical, new tables listed.
It refuses while a Python process is running from the application beside the state folder. There is no downgrade:
going back means restoring the backup (backup_state.py restore).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup_state import digest, running_near  # noqa: E402

OPEN = ("import json,sys;from pathlib import Path;"
        "from market_platform_foundation.local_state.connection import LocalStateConnection;"
        "from market_platform_foundation.local_state.schema import SCHEMA_VERSION;"
        "db=Path(sys.argv[1]);stat=db.stat();"
        "c=LocalStateConnection(db,require_existing=True,expected_identity=(stat.st_dev,stat.st_ino));"
        "print(json.dumps({'schema':c.schema_version(),'code_schema':SCHEMA_VERSION,'integrity':c.integrity_ok()}));c.close()")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--application', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    application, database = args.application.resolve(), args.database.resolve()
    if not (application / 'src/market_platform_foundation/news/supervision.py').is_file():
        raise SystemExit('RELEASE_NOT_APPLIED_TO_APPLICATION')
    if not database.is_file():
        raise SystemExit('DATABASE_NOT_FOUND')
    running = running_near(database)
    if running:
        print(json.dumps({'refused': 'APPLICATION_RUNNING', 'processes': running}, indent=1))
        raise SystemExit(2)
    before, identity = digest(database), (database.stat().st_dev, database.stat().st_ino)
    env = {key: value for key, value in os.environ.items() if not key.startswith('IMP_') and key != 'PYTHONPATH'}
    env.update(PYTHONPATH=os.pathsep.join((str(application), str(application / 'src'))), PYTHONDONTWRITEBYTECODE='1')
    done = subprocess.run([sys.executable, '-B', '-c', OPEN, str(database)], cwd=application, env=env, capture_output=True, text=True)
    if done.returncode:
        print(json.dumps({'migrated': False, 'error': done.stderr.strip().splitlines()[-1:] or ['unknown'],
                          'store_unchanged': digest(database)['tables'] == before['tables']}, indent=1))
        raise SystemExit(1)
    opened, after = json.loads(done.stdout.strip().splitlines()[-1]), digest(database)
    changed = sorted(name for name in before['tables'] if name != 'schema_meta' and after['tables'].get(name) != before['tables'][name])
    added = {name: after['counts'][name] for name in sorted(set(after['tables']) - set(before['tables']))}
    outcome = {'schema_before': before['schema'], 'schema_after': after['schema'], 'release_schema': opened['code_schema'],
               'same_file': (database.stat().st_dev, database.stat().st_ino) == identity, 'integrity': after['integrity'],
               'foreign_key_violations': after['foreign_key_violations'], 'existing_tables': len(before['tables']) - 1,
               'existing_tables_changed': changed, 'tables_added_with_row_counts': added}
    outcome['migrated'] = (outcome['schema_after'] == outcome['release_schema'] and outcome['same_file'] and outcome['integrity'] == 'ok'
                           and not outcome['foreign_key_violations'] and not changed)
    print(json.dumps(outcome, indent=1))
    raise SystemExit(0 if outcome['migrated'] else 1)


if __name__ == '__main__':
    main()
