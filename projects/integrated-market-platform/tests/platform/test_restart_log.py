"""The restart log the owner reviews: one bounded JSONL file of what came back, why, and after how long."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.platform.restart_log import SCHEMA, RestartLog, report


class Clock:
    def __init__(self, value=1_800_000_000.0):
        self.value = value

    def __call__(self):
        return self.value


class RestartLogTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'keeper' / 'restarts.jsonl'
        self.clock = Clock()

    def test_an_entry_says_what_why_when_and_how_long(self):
        log = RestartLog(self.path, clock=self.clock)
        entry = log.record('PLATFORM', 'RESTART', cause='NOT_ANSWERING', outcome='READY', attempt=1, down_seconds=94.24,
                           exit_code=0, message='x' * 1000)
        self.assertEqual((entry['schema'], entry['component'], entry['event'], entry['cause'], entry['outcome'],
                          entry['attempt'], entry['down_seconds']),
                         (SCHEMA, 'PLATFORM', 'RESTART', 'NOT_ANSWERING', 'READY', 1, 94.2))
        self.assertTrue(entry['at'].endswith('Z'))
        self.assertEqual(entry['detail']['exit_code'], 0)
        self.assertEqual(len(entry['detail']['message']), 300)  # bounded: a log line never carries a dump
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8').splitlines()[0]), entry)

    def test_an_unknown_component_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'RESTART_LOG_COMPONENT_UNKNOWN'):
            RestartLog(self.path, clock=self.clock).record('BROKER', 'RESTART')

    def test_the_log_is_bounded_and_read_back_in_order(self):
        log = RestartLog(self.path, max_bytes=2000, keep=2, clock=self.clock)
        for index in range(60):
            self.clock.value += 1
            log.record('COLLECTOR', 'START', cause='PROCESS_GONE', outcome='RUNNING', attempt=index)
        files = sorted(self.path.parent.iterdir())
        self.assertEqual([path.name for path in files], ['restarts.jsonl', 'restarts.jsonl.1', 'restarts.jsonl.2'])
        self.assertTrue(all(path.stat().st_size <= 2000 for path in files))
        attempts = [entry['attempt'] for entry in log.read()]
        self.assertEqual(attempts, sorted(attempts))  # oldest first across the rotated files
        self.assertEqual(attempts[-1], 59)
        self.assertLess(len(attempts), 60)  # the oldest file was dropped

    def test_reading_skips_a_torn_line_and_filters_by_days(self):
        log = RestartLog(self.path, clock=self.clock)
        log.record('PC', 'REBOOT', cause='REBOOT', down_seconds=400)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write('{"torn": \n')
        self.clock.value += 3 * 86400
        log.record('OPEND', 'RESTART', cause='QUOTE_NOT_LOGGED_IN', outcome='RECOVERED')
        self.assertEqual([entry['component'] for entry in log.read()], ['PC', 'OPEND'])
        self.assertEqual([entry['component'] for entry in log.read(days=1)], ['OPEND'])

    def test_the_report_is_a_plain_table(self):
        log = RestartLog(self.path, clock=self.clock)
        log.record('PC', 'REBOOT', cause='REBOOT', outcome='DETECTED', down_seconds=7380)
        log.record('PLATFORM', 'RESTART', cause='REBOOT', outcome='READY', down_seconds=95)
        text = report(log.read())
        lines = text.splitlines()
        self.assertEqual(lines[0].split(), ['When', '(local)', 'What', 'Event', 'Why', 'Result', 'Down'])
        self.assertIn('2h03m', lines[1])
        self.assertIn('95s', lines[2])
        self.assertEqual(report([]), 'No restarts recorded.')


if __name__ == '__main__':
    unittest.main()
