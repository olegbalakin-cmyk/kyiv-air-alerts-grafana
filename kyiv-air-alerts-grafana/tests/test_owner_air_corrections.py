import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from owner_air_corrections import apply_owner_accepted_air_corrections

@dataclass(frozen=True)
class Alert:
    start: datetime
    end: datetime
    source: str = 'vadimkin_official'

DIR = Path(__file__).resolve().parents[1]
PROOF = DIR/'data'/'owner_accepted_air_corrections.json'
START = datetime.fromisoformat('2025-03-05T21:08:24+02:00')
OLD_END = datetime.fromisoformat('2025-03-05T21:47:55+02:00')
NEW_END = datetime.fromisoformat('2025-03-06T05:28:47+02:00')

class AcceptedHistoricalCorrectionTests(unittest.TestCase):
    def test_one_exact_target_corrected(self):
        src = {'kharkiv': [Alert(START, OLD_END)], 'zaporizhzhia': []}
        self.assertEqual(apply_owner_accepted_air_corrections(src, PROOF), 1)
        self.assertEqual(src['kharkiv'][0].end, NEW_END)
        self.assertEqual((src['kharkiv'][0].end-src['kharkiv'][0].start).total_seconds(), 30023)
        self.assertEqual(src['kharkiv'][0].source, 'vadimkin_official')
        self.assertEqual(src['zaporizhzhia'], [])
    def test_idempotent(self):
        src = {'kharkiv': [Alert(START, NEW_END)]}
        self.assertEqual(apply_owner_accepted_air_corrections(src, PROOF), 0)
    def test_unexpected_end_fails_closed(self):
        src = {'kharkiv': [Alert(START, datetime.fromisoformat('2025-03-06T05:03:45+02:00'))]}
        with self.assertRaisesRegex(ValueError, 'unexpected timestamp'):
            apply_owner_accepted_air_corrections(src, PROOF)
    def test_missing_or_duplicate_start_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'found 0'):
            apply_owner_accepted_air_corrections({'kharkiv': []}, PROOF)
        with self.assertRaisesRegex(ValueError, 'found 2'):
            apply_owner_accepted_air_corrections({'kharkiv': [Alert(START,OLD_END), Alert(START,OLD_END)]}, PROOF)
    def test_overlap_fails_closed(self):
        src = {'kharkiv': [Alert(START,OLD_END), Alert(datetime.fromisoformat('2025-03-06T04:15:00+02:00'), datetime.fromisoformat('2025-03-06T04:30:00+02:00'))]}
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            apply_owner_accepted_air_corrections(src, PROOF)
    def test_provenance_mismatch_fails_closed(self):
        obj=json.loads(PROOF.read_text())
        obj['source']['air_off_message_id']=1
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'override.json'
            file.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,'event identity'):
                apply_owner_accepted_air_corrections({'kharkiv': [Alert(START,OLD_END)]}, file)

if __name__ == '__main__':
    unittest.main()
