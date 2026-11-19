"""Receipt semantics: a green compiler or a PASS in prose cannot approve changed code."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_rust_native as native
import validate_native as shared_native
spec = importlib.util.spec_from_file_location('rust_checks', ROOT / 'scripts/check_rust_fixture.py')
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)


class RustReceiptTests(unittest.TestCase):
    def test_required_failure_is_preserved_and_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'src'; root.mkdir(); (root / 'Cargo.toml').write_text('fixture')
            def run(args, **kwargs):
                failed = args[:2] == ['cargo', 'clippy'] and '-D' in args
                return subprocess.CompletedProcess(args, 17 if failed else 0, 'original stdout\n', 'original stderr\n')
            with patch.object(checks.subprocess, 'run', side_effect=run):
                result = checks.check(root, Path(td) / 'logs')
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertEqual(result['checks'][2]['exit_code'], 17)
            self.assertEqual((Path(td) / 'logs/02-clippy.log').read_text(), 'original stdout\noriginal stderr\n')
            self.assertEqual(len(result['checks']), 6)

    def test_changed_source_invalidates_green_commands(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'src'; root.mkdir(); manifest = root / 'Cargo.toml'; manifest.write_text('old')
            def run(args, **kwargs):
                if args[:2] == ['cargo', 'build']: manifest.write_text('changed')
                return subprocess.CompletedProcess(args, 0, 'ok', '')
            with patch.object(checks.subprocess, 'run', side_effect=run):
                result = checks.check(root, Path(td) / 'logs')
            self.assertFalse(result['source_unchanged'])
            self.assertEqual(result['status'], 'BLOCKED')

    def test_evidence_cannot_pollute_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError): checks.check(root, root / 'logs')

    def test_installer_delivers_rust_entry_and_references(self):
        import install
        with tempfile.TemporaryDirectory() as td:
            home = Path(td).resolve(); result = install.install(home)
            entry = home / '.codex/skills/codex-rust-workflow/SKILL.md'
            self.assertTrue(entry.is_file())
            for name in ('cargo-gates.md', 'review.md'):
                self.assertEqual((entry.parent / 'references' / name).read_bytes(),
                                 (ROOT / 'skills/codex-rust-workflow/references' / name).read_bytes())
            self.assertTrue((Path(result['release']) / 'skills/codex-rust-workflow/SKILL.md').is_file())

    def test_installer_omits_build_and_private_artifacts(self):
        import install
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td)
            (fake / 'tools.py').write_text('public')
            for rel in ('examples/demo/Cargo.toml', 'examples/demo/target/debug/binary', 'examples/demo/.private/log'):
                p = fake / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('fixture')
            with patch.object(install, 'ROOT', fake): payload = install.payload()
            self.assertEqual(set(payload), {'tools.py', 'examples/demo/Cargo.toml'})

    def test_missing_or_wrong_actual_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td)
            for events in ([], [{'type':'thread.started','thread_id':'other'}]):
                (evidence / 'phase.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
                with patch.object(native, 'native_call', return_value={'session':'expected'}):
                    with self.assertRaises(RuntimeError):
                        native.call(Path(td), Path(td), evidence, 'phase', 'prompt', session='expected')

    def test_prose_pass_does_not_approve(self):
        with self.assertRaises(RuntimeError):
            native.verdict({'messages':['Earlier PASS; actual result BLOCKED']}, 'PASS')
        native.verdict({'messages':['Reviewed original logs.\nVERDICT: PASS']}, 'PASS')

    def test_active_staging_home_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td).resolve(); (home / '.codex').mkdir()
            with patch.dict(native.os.environ, {'CODEX_HOME':str(home / '.codex')}):
                with self.assertRaises(ValueError): native.staging_home(home)

    def test_isolated_auth_uses_file_store_and_removes_standard_keys(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def run(argv, **kwargs):
                self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
                self.assertNotIn('CODEX_API_KEY', kwargs['env'])
                self.assertIn('cli_auth_credentials_store="file"', argv)
                self.assertEqual(kwargs['env']['CODEX_HOME'], str(root / '.codex'))
                kwargs['stdout'].write(json.dumps({'type':'thread.started','thread_id':'fixture-session'}) + '\n')
                return subprocess.CompletedProcess(argv, 0)
            with patch.dict(shared_native.os.environ, {'OPENAI_API_KEY':'fixture-value','CODEX_API_KEY':'fixture-value'}), patch.object(shared_native.subprocess, 'run', side_effect=run):
                shared_native.call(root, root, root, 'auth-test', 'fixture', isolated_auth=True)


if __name__ == '__main__': unittest.main()
