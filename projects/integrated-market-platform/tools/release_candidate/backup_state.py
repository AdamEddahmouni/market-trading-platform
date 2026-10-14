"""Back up, verify or restore one IMP local-state database. Owner-run; nothing here runs by itself.

  backup_state.py backup  --database <state folder>\\imp-state.sqlite3 --out <new folder>
  backup_state.py verify  --backup-dir <folder backup wrote>
  backup_state.py restore --database <state folder>\\imp-state.sqlite3 --backup-dir <folder> --set-aside <new folder>

backup opens the source read-only and copies it through SQLite's backup API (WAL content included), then proves the
copy: integrity, schema version, and the same logical content per table as the source. restore moves the current
database and its -wal/-shm files into the set-aside folder (nothing is deleted) and puts the backup in its place.
backup and restore refuse while a Python process is running from the application that owns the state folder.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

RECORD = 'BACKUP.json'


def digest(path):
    """Schema version, integrity and a logical digest per table, read-only."""
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        tables, counts = {}, {}
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(json.dumps(list(row), sort_keys=True, default=str) for row in conn.execute('SELECT * FROM ' + quoted))
            schema = conn.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0]
            counts[name] = len(rows)
            tables[name] = hashlib.sha256(json.dumps([schema, rows]).encode()).hexdigest()
        return {'schema': conn.execute('SELECT MAX(schema_version) FROM schema_meta').fetchone()[0],
                'integrity': conn.execute('PRAGMA integrity_check').fetchone()[0],
                'foreign_key_violations': len(conn.execute('PRAGMA foreign_key_check').fetchall()),
                'tables': tables, 'counts': counts}


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def running_near(database):
    """Python processes started from the application beside this state folder (<root>\\projects\\...)."""
    application = (str(database.resolve().parent.parent) + '\\projects\\').lower()
    inventory = subprocess.run(['powershell', '-NoProfile', '-Command',
                              "$ErrorActionPreference='Stop'; Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                              "ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"],
                             capture_output=True, text=True)
    listing = inventory.stdout.splitlines()
    if (inventory.returncode or inventory.stderr.strip()
            or any(not line.partition('|')[0].isdigit() or not line.partition('|')[1]
                   or not line.partition('|')[2].strip() for line in listing)):
        raise RuntimeError('PROCESS_INVENTORY_UNAVAILABLE')
    own = str(os.getpid())  # this tool's own command line names the application or its state folder
    return [line.partition('|')[2].strip()[:160] for line in listing
            if line.partition('|')[0] != own and application in line.lower().replace('/', '\\')]


def backup(database, out):
    out.mkdir(parents=True, exist_ok=False)
    source = digest(database)
    target = out / f"imp-state.schema{source['schema']}.sqlite3"
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
    copy = digest(target)
    record = {'database': str(database), 'backup': target.name, 'taken_utc': datetime.now(timezone.utc).isoformat(),
              'bytes': target.stat().st_size, 'sha256': file_sha(target), 'schema': copy['schema'], 'integrity': copy['integrity'],
              'foreign_key_violations': copy['foreign_key_violations'], 'counts': copy['counts'], 'tables': copy['tables'],
              'identical_to_source': copy['tables'] == source['tables'] and copy['schema'] == source['schema']}
    (out / RECORD).write_text(json.dumps(record, indent=1), encoding='utf-8')
    return record


def verify(backup_dir):
    record = json.loads((backup_dir / RECORD).read_text(encoding='utf-8'))
    target = backup_dir / record['backup']
    now = digest(target)
    return {'backup': str(target), 'sha256_unchanged': file_sha(target) == record['sha256'], 'integrity': now['integrity'],
            'schema': now['schema'], 'content_unchanged': now['tables'] == record['tables'],
            'ok': file_sha(target) == record['sha256'] and now['integrity'] == 'ok' and now['tables'] == record['tables']}


def restore(database, backup_dir, set_aside):
    checked = verify(backup_dir)
    if not checked['ok']:
        return {'restored': False, 'reason': 'BACKUP_FAILED_VERIFICATION', **checked}
    set_aside.mkdir(parents=True, exist_ok=False)
    moved = []
    for suffix in ('', '-wal', '-shm'):
        current = Path(str(database) + suffix)
        if current.exists():
            shutil.move(str(current), set_aside / current.name)
            moved.append(current.name)
    shutil.copyfile(checked['backup'], database)
    after = digest(database)
    record = json.loads((backup_dir / RECORD).read_text(encoding='utf-8'))
    return {'restored': after['tables'] == record['tables'] and after['integrity'] == 'ok', 'schema': after['schema'],
            'set_aside': str(set_aside), 'moved': moved}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('backup', 'verify', 'restore'))
    parser.add_argument('--database', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--set-aside', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        outcome = verify(args.backup_dir.resolve())
        print(json.dumps(outcome, indent=1))
        raise SystemExit(0 if outcome['ok'] else 1)
    database = args.database.resolve()
    if not database.is_file():
        raise SystemExit('DATABASE_NOT_FOUND')
    running = running_near(database)
    if running:
        print(json.dumps({'refused': 'APPLICATION_RUNNING', 'processes': running}, indent=1))
        raise SystemExit(2)
    if args.command == 'backup':
        record = backup(database, args.out.resolve())
        print(json.dumps({key: record[key] for key in ('backup', 'bytes', 'sha256', 'schema', 'integrity', 'identical_to_source')}
                         | {'rows': sum(record['counts'].values()), 'tables': len(record['counts'])}, indent=1))
        raise SystemExit(0 if record['identical_to_source'] and record['integrity'] == 'ok' else 1)
    outcome = restore(database, args.backup_dir.resolve(), args.set_aside.resolve())
    print(json.dumps(outcome, indent=1))
    raise SystemExit(0 if outcome['restored'] else 1)


if __name__ == '__main__':
    main()
