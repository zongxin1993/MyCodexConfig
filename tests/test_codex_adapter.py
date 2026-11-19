import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import install
import tools


class InstallerTests(unittest.TestCase):
    def home(self, base):
        home = Path(base).resolve() / 'home'; (home / '.codex').mkdir(parents=True)
        (home / '.codex/config.toml').write_text('model = "existing-model"\n[features]\nhooks = true\n')
        (home / '.codex/AGENTS.md').write_text('Existing user rules\n')
        (home / '.codex/hooks.json').write_text('{"do":"not change"}')
        return home

    def test_backup_install_idempotent_rollback_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            old = {p: p.read_bytes() for p in (home / '.codex').iterdir()}
            oc = home / '.config/opencode/opencode.json'; oc.parent.mkdir(parents=True); oc.write_text('{"unchanged":true}')
            result = install.install(home)
            self.assertEqual(result['status'], 'INSTALLED')
            self.assertIn('existing-model', (home / '.codex/config.toml').read_text())
            self.assertIn('Existing user rules', (home / '.codex/AGENTS.md').read_text())
            self.assertEqual(json.loads((home / '.config/mycodexconfig/settings.json').read_text()), {'projects': []})
            self.assertTrue((home / '.codex/skills/codex-workflow/SKILL.md').is_file())
            self.assertEqual(install.install(home)['status'], 'UNCHANGED')
            self.assertEqual(install.rollback(home, result['backup'])['status'], 'ROLLED_BACK')
            for p, value in old.items(): self.assertEqual(p.read_bytes(), value)
            self.assertEqual(oc.read_text(), '{"unchanged":true}')
            self.assertFalse((home / '.config/mycodexconfig/settings.json').exists())

    def test_foreign_mcp_or_skill_refused_before_change(self):
        for kind in ('mcp', 'skill'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                home = self.home(td)
                if kind == 'mcp':
                    p = home / '.codex/config.toml'; p.write_text(p.read_text() + '\n[mcp_servers.quality]\ncommand="foreign"\n')
                else:
                    p = home / '.codex/skills/codex-workflow'; p.mkdir(parents=True); (p / 'SKILL.md').write_text('foreign')
                before = (home / '.codex/config.toml').read_bytes()
                with self.assertRaises(ValueError): install.install(home)
                self.assertEqual((home / '.codex/config.toml').read_bytes(), before)
                self.assertFalse((home / '.config/mycodexconfig/settings.json').exists())

    def test_registry_preserved_and_concurrent_change_blocks_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td); settings = home / '.config/mycodexconfig/settings.json'; settings.parent.mkdir(parents=True)
            settings.write_text('{"projects":[]}\n'); before = settings.read_bytes()
            result = install.install(home, context7=False)
            self.assertEqual(settings.read_bytes(), before)
            self.assertNotIn('[mcp_servers.context7]', (home / '.codex/config.toml').read_text())
            (home / '.codex/AGENTS.md').write_text('Concurrent user edit')
            with self.assertRaises(ValueError): install.rollback(home, result['backup'])
            self.assertIn('[mcp_servers.quality]', (home / '.codex/config.toml').read_text())

    def test_symlinks_and_ambiguous_markers_refused(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td); external = Path(td) / 'external'; external.write_text('external')
            p = home / '.codex/config.toml'; p.unlink(); p.symlink_to(external)
            with self.assertRaises(ValueError): install.install(home)
            self.assertEqual(external.read_text(), 'external')
        with self.assertRaises(ValueError): install.managed(install.START, 'new')

    def test_modified_runtime_refused(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td); result = install.install(home)
            (Path(result['release']) / 'tools.py').write_text('tampered')
            with self.assertRaises(ValueError): install.install(home)

    def test_toml_variants_and_malformed_config_refused(self):
        for content in ('[mcp_servers."quality"]\ncommand="foreign"',
                        '["mcp_servers"."context7"]\nurl="https://example.invalid"',
                        'mcp_servers={quality={command="foreign"}}',
                        'model = [broken'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as td:
                home = self.home(td)
                path = home / '.codex/config.toml'; path.write_text(content)
                with self.assertRaises(ValueError): install.install(home)
                self.assertEqual(path.read_text(), content)

    def test_missing_runtime_is_restored(self):
        import shutil
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td); first = install.install(home)
            shutil.rmtree(first['release'])
            restored = install.install(home)
            self.assertEqual(restored['status'], 'RUNTIME_RESTORED')
            self.assertTrue((Path(restored['release']) / 'workflow/server.py').is_file())

    def test_installed_resource_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td); result = install.install(home)
            release = Path(result['release'])
            resource = release / 'resources/bmad/quick/workflow.md'
            resource.write_text(resource.read_text() + '\nTampered')
            script = "from workflow.runtime import Runtime; Runtime({'projects': []}).resource('bmad/quick/workflow.md')"
            run = subprocess.run([sys.executable, '-c', script], cwd=release, capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('integrity', run.stderr.lower())

    def test_bmad_public_resources_are_available_without_opencode(self):
        from workflow.runtime import Runtime
        runtime = Runtime({'projects': []})
        for mode in ('quick', 'thorough'):
            value = runtime.resource('bmad/' + mode + '/workflow.md')
            self.assertTrue(value['content'])
            self.assertNotIn('/Users/', value['content'])
        with self.assertRaises(ValueError): runtime.resource('../../credentials')

    def test_codex_skills_do_not_call_opencode_only_tools(self):
        for name in ('codex-execution', 'codex-ast-grep'):
            text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
            self.assertIn('native', text)
        self.assertNotIn('opencode-quality/settings', (ROOT / 'install.py').read_text())


class ToolsTests(unittest.TestCase):
    def test_paths_escape_secret_directory_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'tree'; root.mkdir(); ((root / 'a.py').resolve()).write_text('ok')
            outside = Path(td) / 'private'; outside.write_text('secret'); (root / 'link').symlink_to(outside)
            self.assertEqual(tools.source(root, 'a.py'), (root / 'a.py').resolve())
            for path in ('../private', str(outside), 'link', '.env', '.git/config'):
                with self.subTest(path=path), self.assertRaises((ValueError, FileNotFoundError)):
                    tools.source(root, path)

    def test_existing_worktree_detection_and_primary_detection(self):
        with tempfile.TemporaryDirectory() as td:
            main = Path(td) / 'main'; main.mkdir()
            def git(*args): return subprocess.check_output(['git', '-C', str(main), *args], stderr=subprocess.DEVNULL, text=True)
            git('init'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
            (main / 'a.py').write_text('x=1'); git('add', '.'); git('commit', '-m', 'fixture')
            wt = Path(td) / 'task'; git('worktree', 'add', '-b', 'fixture/task', str(wt))
            for path, expected in ((main, False), (wt, True)):
                result = subprocess.run([sys.executable, str(ROOT / 'tools.py'), 'worktree', '--root', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIs(json.loads(result.stdout)['isolated'], expected)
            self.assertEqual(git('status', '--porcelain'), '')


if __name__ == '__main__': unittest.main()
