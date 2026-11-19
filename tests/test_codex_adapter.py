import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_native_multiline_values_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            install.install(home)
            config = home / '.codex/config.toml'
            native = '[tui]\nvalue = """hello\n[brackets]\n"""\narray = [\n[1, 2],\n[3, 4]\n]\n'
            config.write_text(config.read_text().replace(install.END, native + install.END))
            install.install(home, workflow_hooks=True)
            self.assertEqual(install.tomllib.loads(config.read_text())['tui'],
                             install.tomllib.loads(native)['tui'])

    def test_managed_mcp_extensions_refused_without_loss(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            install.install(home)
            config = home / '.codex/config.toml'
            original = config.read_text().replace(install.END, '[mcp_servers.quality.env]\nCUSTOM = "fixture"\n' + install.END)
            config.write_text(original)
            with self.assertRaisesRegex(ValueError, 'Ambiguous managed MCP extension'):
                install.install(home, workflow_hooks=True)
            self.assertEqual(config.read_text(), original)

    def test_failed_install_rollback_preserves_newer_config(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            config = home / '.codex/config.toml'
            hooks = home / '.codex/hooks.json'
            actual = install.atomic
            newer = []
            def update(path, data):
                actual(path, data)
                if path == config:
                    newer.append(data + b'\n[tui]\nscreen_reader_detection_done = true\n')
                    config.write_bytes(newer[-1])
                    hooks.write_text('{"hooks":{},"description":"concurrent"}')
            with patch.object(install, 'atomic', side_effect=update):
                with self.assertRaisesRegex(ValueError, 'Partial rollback; preserved concurrent edits'):
                    install.install(home, workflow_hooks=True)
            self.assertEqual(config.read_bytes(), newer[-1])
            self.assertEqual(json.loads(hooks.read_text())['description'], 'concurrent')

    def test_config_concurrent_update_refused_at_both_checkpoints(self):
        for checkpoint in ('payload', 'deploy_release'):
            with self.subTest(checkpoint=checkpoint), tempfile.TemporaryDirectory() as td:
                home = self.home(td)
                config = home / '.codex/config.toml'
                original = config.read_bytes()
                newer = original + b'\n[tui]\nscreen_reader_detection_done = true\n'
                actual = getattr(install, checkpoint)
                def update(*args, **kwargs):
                    config.write_bytes(newer)
                    return actual(*args, **kwargs)
                with patch.object(install, checkpoint, side_effect=update):
                    with self.assertRaisesRegex(ValueError, 'Concurrent change'):
                        install.install(home, workflow_hooks=True)
                self.assertEqual(config.read_bytes(), newer)

    def test_upgrade_preserves_native_tables_inserted_inside_managed_markers(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            install.install(home)
            config = home / '.codex/config.toml'
            native = ('[tui]\nscreen_reader_detection_done = true\n'
                      '[hooks.state."native"]\ntrusted_hash = "fixture-trust"\n'
                      '[[skills.config]]\npath = "/fixture/personal/SKILL.md"\nenabled = true\n')
            config.write_text(config.read_text().replace(install.END, native + install.END))
            result = install.install(home, workflow_hooks=True)
            parsed = install.tomllib.loads(config.read_text())
            self.assertTrue(parsed['tui']['screen_reader_detection_done'])
            self.assertEqual(parsed['hooks']['state']['native']['trusted_hash'], 'fixture-trust')
            self.assertIn({'path': '/fixture/personal/SKILL.md', 'enabled': True}, parsed['skills']['config'])
            self.assertEqual(parsed['model'], 'existing-model')
            self.assertEqual(install.install(home)['status'], 'UNCHANGED')
            self.assertEqual(install.rollback(home, result['backup'])['status'], 'ROLLED_BACK')
            self.assertIn(native, config.read_text())

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

    def test_workflow_hooks_opt_in_preserves_foreign_hooks_and_rolls_back(self):
        with tempfile.TemporaryDirectory(prefix="fixture's home ") as td:
            home = self.home(td)
            path = home / '.codex/hooks.json'
            rtk = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'rtk hook codex'}]}
            other = {'hooks': [{'type': 'command', 'command': 'another hook'}]}
            original = {'description': 'Personal hooks',
                        'hooks': {'PreToolUse': [rtk], 'SessionEnd': [other], 'Stop': [other]}}
            before = json.dumps(original).encode()
            path.write_bytes(before)
            config = path.with_name('config.toml')
            trust = '\n[hooks.state."pre_tool_use:0:0"]\ntrusted_hash = "test-trust"\n'
            config.write_text(config.read_text() + trust)
            result = install.install(home, workflow_hooks=True)
            merged = json.loads(path.read_text())
            self.assertEqual(merged['description'], original['description'])
            self.assertEqual(merged['hooks']['PreToolUse'][0], rtk)
            self.assertEqual(merged['hooks']['SessionEnd'], [other])
            self.assertEqual(merged['hooks']['Stop'][0], other)
            self.assertTrue(result['warnings'])
            self.assertIn('SubagentStart', merged['hooks'])
            self.assertIn(trust, config.read_text())
            for event in install.GUARD_EVENTS:
                handler, = merged['hooks'][event][-1]['hooks']
                self.assertEqual(handler['statusMessage'], install.GUARD_STATUS)
                self.assertEqual(handler['timeout'], 3 if event == 'Interrupt' else 10)
                self.assertEqual(shlex.split(handler['command']), [
                    str(Path(sys.executable).resolve()), str(Path(result['release']) / 'workflow/guard.py'),
                    'hook', '--state-dir', str(home / '.local/state/mycodexconfig/guard')])
            installed = path.read_bytes()
            repeated = install.install(home)
            self.assertEqual(repeated['status'], 'UNCHANGED')
            self.assertEqual(repeated['warnings'], result['warnings'])
            self.assertEqual(path.read_bytes(), installed)
            disabled = install.install(home, workflow_hooks=False)
            self.assertEqual(json.loads(path.read_text()), original)
            install.rollback(home, disabled['backup'])
            self.assertEqual(path.read_bytes(), installed)
            install.rollback(home, result['backup'])
            self.assertEqual(path.read_bytes(), before)

    def test_disabling_guard_preserves_foreign_hook_group_indices(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            path = home / '.codex/hooks.json'
            install.install(home, workflow_hooks=True)
            config = json.loads(path.read_text())
            foreign = {'hooks': [{'type': 'command', 'command': 'another hook'}]}
            config['hooks']['Stop'].append(foreign)
            path.write_text(json.dumps(config))
            self.assertEqual(install.install(home, workflow_hooks=True)['status'], 'UNCHANGED')
            install.install(home, workflow_hooks=False)
            self.assertEqual(json.loads(path.read_text())['hooks']['Stop'], [{'hooks': []}, foreign])

    def test_workflow_hooks_default_upgrade_updates_command_and_reports_trust(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            path = home / '.codex/hooks.json'
            first = install.install(home, workflow_hooks=True)
            config = path.with_name('config.toml')
            trust = '\n[hooks.state."session_start:0:0"]\ntrusted_hash = "test-trust"\n'
            config.write_text(config.read_text() + trust)
            upgraded = install.payload()
            upgraded['tools.py'] += b'\n# Upgrade fixture\n'
            with patch.object(install, 'payload', side_effect=lambda _: upgraded.copy()):
                result = install.install(home)
                self.assertEqual(install.install(home)['status'], 'UNCHANGED')
            self.assertNotEqual(result['release'], first['release'])
            self.assertTrue(any('Review hook trust again' in warning for warning in result['warnings']))
            command = json.loads(path.read_text())['hooks']['SessionStart'][0]['hooks'][0]['command']
            self.assertEqual(shlex.split(command)[1], str(Path(result['release']) / 'workflow/guard.py'))
            self.assertIn(trust, config.read_text())

    def test_workflow_hooks_warn_about_foreign_toml(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            config = home / '.codex/config.toml'
            foreign = ('model = "existing-model"\n[features]\nhooks = false\n'
                       '[[hooks.Stop]]\n[[hooks.Stop.hooks]]\n'
                       'type = "command"\ncommand = "foreign hook"\n')
            config.write_text(foreign)
            result = install.install(home, workflow_hooks=True)
            self.assertTrue(any('features.hooks = false' in warning for warning in result['warnings']))
            self.assertTrue(any('Inline config.toml hooks' in warning for warning in result['warnings']))
            self.assertTrue(config.read_text().startswith(foreign))

    def test_workflow_hooks_cli_enable_preserve_disable(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            hook_file = home / '.codex/hooks.json'
            command = [sys.executable, str(ROOT / 'install.py'), '--home', str(home)]
            baseline = hook_file.read_bytes()
            subprocess.check_call(command, stdout=subprocess.DEVNULL)
            self.assertEqual(hook_file.read_bytes(), baseline)
            subprocess.check_call(command + ['--workflow-hooks'], stdout=subprocess.DEVNULL)
            enabled = hook_file.read_bytes()
            self.assertNotEqual(enabled, baseline)
            subprocess.check_call(command, stdout=subprocess.DEVNULL)
            self.assertEqual(hook_file.read_bytes(), enabled)
            subprocess.check_call(command + ['--without-workflow-hooks'], stdout=subprocess.DEVNULL)
            self.assertEqual(json.loads(hook_file.read_bytes()), {'do': 'not change', 'hooks': {}})

    def test_workflow_hooks_malformed_or_collision_refused_before_changes(self):
        foreign = {'hooks': {'Stop': [{'hooks': [
            {'type': 'command', 'command': 'unrelated', 'statusMessage': install.GUARD_STATUS}
        ]}]}}
        for content in ('{', '{"hooks":[]}', '{"hooks":{"Stop":[{}]}}', '{"hooks":{},"hooks":{}}',
                        json.dumps(foreign)):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as td:
                home = self.home(td)
                path = home / '.codex/hooks.json'
                path.write_text(content)
                before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
                with self.assertRaises(ValueError):
                    install.install(home, workflow_hooks=True)
                self.assertEqual({p.name: p.read_bytes() for p in path.parent.iterdir()}, before)
                self.assertFalse((home / '.local').exists())

    def test_workflow_hooks_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            external = Path(td).resolve() / 'foreign-hooks.json'
            path = home / '.codex/hooks.json'
            path.rename(external)
            path.symlink_to(external)
            before = external.read_bytes()
            with self.assertRaises(ValueError):
                install.install(home, workflow_hooks=True)
            self.assertTrue(path.is_symlink())
            self.assertEqual(external.read_bytes(), before)
            self.assertFalse((home / '.local').exists())

    def test_workflow_hooks_install_failure_and_concurrent_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            home = self.home(td)
            path = home / '.codex/hooks.json'
            config = path.with_name('config.toml')
            before = path.read_bytes(), config.read_bytes()
            atomic = install.atomic
            def fail_after_hooks(target, data):
                if target == path.with_name('AGENTS.md'):
                    raise OSError('fixture install failure')
                atomic(target, data)
            with patch.object(install, 'atomic', side_effect=fail_after_hooks), self.assertRaises(OSError):
                install.install(home, workflow_hooks=True)
            self.assertEqual((path.read_bytes(), config.read_bytes()), before)
            result = install.install(home, workflow_hooks=True)
            path.write_text('{"description":"concurrent user edit"}')
            with self.assertRaisesRegex(ValueError, 'Concurrent change'):
                install.rollback(home, result['backup'])
            self.assertIn('[mcp_servers.quality]', config.read_text())

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
