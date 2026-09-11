"""Small offline tests for upstream validation; creates no archives."""
import csv
import hashlib
from pathlib import Path
import tempfile
import unittest
from fetch_sources import safe_member, valid
from verify_inputs import partition, verify

class UpstreamTests(unittest.TestCase):
    def test_member_paths(self):
        for name in ('../a', '/a', 'a/../b', 'C:/a', 'a\\b'):
            self.assertFalse(safe_member(name))
        self.assertTrue(safe_member('source/train.pkl'))

    def test_source_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.txt'
            path.write_bytes(b'abc')
            record = {'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
            self.assertTrue(valid(path, record))
            path.write_bytes(b'abd')
            self.assertFalse(valid(path, record))

    def test_bijective_partition(self):
        a = [{'participant_id': x} for x in ('a', 'a', 'b')]
        b = [{'participant_id': x} for x in ('q', 'q', 'r')]
        c = [{'participant_id': x} for x in ('q', 'r', 'r')]
        self.assertEqual(partition(a), partition(b))
        self.assertNotEqual(partition(a), partition(c))

    def test_scientific_value_and_group_changes_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            ref, out = Path(folder) / 'reference', Path(folder) / 'candidate'
            ref.mkdir(); out.mkdir()
            name = 'crosscheck_pairs_public.csv'
            fields = ['row_id', 'participant_id', 'T']
            def write(parent, rows):
                with (parent / name).open('w', newline='') as f:
                    writer = csv.writer(f); writer.writerow(fields); writer.writerows(rows)
            write(ref, [[1, 'a', 1], [2, 'a', 2], [3, 'b', 3]])
            write(out, [[1, 'x', 1], [2, 'x', 2], [3, 'y', 3]])
            self.assertEqual(verify(ref, out, 'crosscheck')['status'], 'PASS')
            write(out, [[1, 'x', 1], [2, 'x', 3], [3, 'y', 3]])
            self.assertEqual(verify(ref, out, 'crosscheck')['status'], 'FAIL')
            write(out, [[1, 'x', 1], [2, 'y', 2], [3, 'y', 3]])
            self.assertEqual(verify(ref, out, 'crosscheck')['status'], 'FAIL')

if __name__ == '__main__':
    unittest.main()
