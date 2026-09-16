"""归档与撤销的文件保护回归测试，不依赖 SQL 翻译引擎。"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs_database_script_organizer import organizer


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.src = self.root / 'temp/draft.groovy'
        self.bak = self.root / 'backup/draft.groovy'
        self.out = self.root / 'migration/new.groovy'
        self.schema = self.root / 'business/schema_version.sql'
        self.sharding = self.root / '行业应用/saas-sharding.yml.vm'
        for path, content in [(self.src, b'draft'), (self.schema, b'\xef\xbb\xbfold\r\n'),
                              (self.sharding, b'')]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def apply(self):
        organizer.apply_plan(self.root, {
            self.out: b'generated', self.schema: b'\xef\xbb\xbfold\r\nnew\n',
            self.sharding: b'updated',
        }, [(self.src, self.bak)], [{'file': 'business/schema_version.sql', 'lines': ['new\n']}],
            '', 'updated', {})

    def undo(self):
        with contextlib.redirect_stdout(io.StringIO()):
            organizer.undo_last_organize(self.root)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_round_trip_restores_exact_bytes_including_empty_config(self):
        self.src.chmod(0o640)
        before = self.snapshot()
        self.apply()
        self.undo()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(0o640, self.src.stat().st_mode & 0o777)

    def test_write_failure_restores_all_preexisting_files(self):
        before = self.snapshot()
        original = organizer._atomic_write
        def fail_schema(path, content):
            if path == self.schema and content.endswith(b'new\n'):
                raise OSError('simulated write failure')
            original(path, content)
        with patch.object(organizer, '_atomic_write', side_effect=fail_schema):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(before, self.snapshot())

    def test_undo_latest_archive_preserves_earlier_batch(self):
        self.apply()
        first = self.snapshot()
        first.pop(organizer.RECEIPT_FILENAME)
        second = self.root / 'migration/second.groovy'
        organizer.apply_plan(self.root, {second: b'second'}, [], [], None, None, {})
        self.undo()
        self.assertEqual(first, self.snapshot())
        with self.assertRaises(organizer.OrganizeError):
            self.undo()

    def test_symlink_in_receipt_target_is_rejected(self):
        self.apply()
        self.out.unlink()
        self.out.symlink_to(self.schema)
        before = self.snapshot()
        with self.assertRaises(organizer.OrganizeError):
            self.undo()
        self.assertTrue(self.out.is_symlink())
        self.assertEqual(before, self.snapshot())

    def test_sharding_preview_outputs_diff_without_changing_files(self):
        before = self.snapshot()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            organizer.print_sharding_diff('before\n', 'after\n', 'saas-sharding.yml.vm')
        self.assertIn('-before', output.getvalue())
        self.assertIn('+after', output.getvalue())
        self.assertEqual(before, self.snapshot())

    def test_user_edits_block_entire_undo(self):
        for changed in [self.src, self.out, self.schema, self.sharding, self.bak]:
            with self.subTest(path=changed):
                self.apply()
                changed.write_bytes(b'user change')
                before = self.snapshot()
                with self.assertRaises(organizer.OrganizeError):
                    self.undo()
                self.assertEqual(before, self.snapshot())
                # 每次恢复到独立的归档前状态，仅处理本测试临时文件。
                for p in self.root.rglob('*'):
                    if p.is_file():
                        p.unlink()
                self.src.write_bytes(b'draft')
                self.schema.write_bytes(b'\xef\xbb\xbfold\r\n')
                self.sharding.write_bytes(b'')

    def test_missing_backup_blocks_entire_undo(self):
        self.apply()
        self.bak.unlink()
        before = self.snapshot()
        with self.assertRaises(organizer.OrganizeError):
            self.undo()
        self.assertEqual(before, self.snapshot())

    def test_receipt_failure_rolls_back_and_preserves_previous_receipt(self):
        receipt = self.root / organizer.RECEIPT_FILENAME
        receipt.write_bytes(b'previous receipt')
        before = self.snapshot()
        original = organizer._atomic_write
        def fail_receipt(path, content):
            if path == receipt and content != b'previous receipt':
                raise OSError('simulated receipt failure')
            original(path, content)
        with patch.object(organizer, '_atomic_write', side_effect=fail_receipt):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(before, self.snapshot())

    def test_undo_failure_restores_archived_state_and_receipt(self):
        self.apply()
        before = self.snapshot()
        original = organizer._atomic_write
        def fail_schema(path, content):
            if path == self.schema and content == b'\xef\xbb\xbfold\r\n':
                raise OSError('simulated undo failure')
            original(path, content)
        with patch.object(organizer, '_atomic_write', side_effect=fail_schema):
            with self.assertRaises(OSError):
                self.undo()
        self.assertEqual(before, self.snapshot())

    def test_legacy_receipt_refused_without_changes(self):
        (self.root / organizer.RECEIPT_FILENAME).write_text('{"moves": [], "writes": []}')
        before = self.snapshot()
        with self.assertRaises(organizer.OrganizeError):
            self.undo()
        self.assertEqual(before, self.snapshot())

    def test_undo_dry_run_does_not_mutate(self):
        from bs_database_script_organizer.cli import main
        self.apply()
        before = self.snapshot()
        with self.assertRaises(organizer.OrganizeError):
            main(['--database-root', str(self.root), '--undo', '--dry-run'])
        self.assertEqual(before, self.snapshot())

    def test_backup_collision_rejected(self):
        self.bak.parent.mkdir()
        self.bak.write_bytes(b'older backup')
        before = self.snapshot()
        with self.assertRaises(organizer.OrganizeError):
            self.apply()
        self.assertEqual(before, self.snapshot())

    def test_undo_receipt_path_escape_rejected(self):
        import json
        self.apply()
        receipt = self.root / organizer.RECEIPT_FILENAME
        data = json.loads(receipt.read_text())
        data['files'][0]['path'] = '../outside.groovy'
        receipt.write_text(json.dumps(data))
        before = self.snapshot()
        with self.assertRaises(organizer.OrganizeError):
            self.undo()
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
