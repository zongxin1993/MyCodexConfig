import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from workflow.runtime import Runtime
from workflow.registration import onboard
from test_quality import policy


def native(root):
    return {'root':str(root), 'integration': {'mode':'repository-native',
            'authorities':['AGENTS.md'], 'instructions':'Preserve project governance.'}}


class RegistryAvailability(unittest.TestCase):
    def test_stale_entries_preserved_without_breaking_healthy_onboarding(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve(); healthy=base/'healthy'; healthy.mkdir()
            (healthy/'README.md').write_text('project')
            stale=base/'removed'
            settings={'projects':[{'root':str(stale),'policy':policy()}]}
            registry=base/'settings.json'; registry.write_text(json.dumps(settings))
            r=Runtime(settings,settings_path=registry)
            self.assertIn(str(stale),r.info()['unavailable_projects'])
            with self.assertRaisesRegex(ValueError,'unavailable'): r.root(str(stale))
            self.assertEqual(onboard(registry,str(healthy))['onboarding'],'registered')
            self.assertEqual(json.loads(registry.read_text())['projects'][0],settings['projects'][0])
            self.assertEqual(r.root(str(healthy)),healthy)

    def test_missing_authority_blocks_ancestor_and_linked_profile(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve(); main=base/'main'; main.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(main),*args],stderr=subprocess.DEVNULL,text=True)
            git('init'); git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            (main/'AGENTS.md').write_text('rules');git('add','.');git('commit','-m','fixture')
            wt=base/'wt';git('worktree','add','-b','fixture',str(wt))
            settings={'projects':[native(main)]};registry=base/'settings.json';registry.write_text(json.dumps(settings))
            (main/'AGENTS.md').unlink(); before=registry.read_bytes()
            for target in (main,wt):
                with self.subTest(target=target),self.assertRaisesRegex(ValueError,'unavailable'):
                    onboard(registry,str(target))
            self.assertEqual(registry.read_bytes(),before)
            (main/'AGENTS.md').write_text('rules')
            self.assertEqual(onboard(registry,str(wt))['onboarding'],'registered')

    def test_linked_destination_missing_authority_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve(); main=base/'main';main.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(main),*args],stderr=subprocess.DEVNULL,text=True)
            git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            (main/'AGENTS.md').write_text('rules');git('add','.');git('commit','-m','fixture')
            wt=base/'wt';git('worktree','add','-b','fixture',str(wt));(wt/'AGENTS.md').unlink()
            registry=base/'settings.json';registry.write_text(json.dumps({'projects':[native(main)]}));before=registry.read_bytes()
            with self.assertRaisesRegex(ValueError,'unavailable'):onboard(registry,str(wt))
            self.assertEqual(registry.read_bytes(),before)
            self.assertFalse((base/'backups').exists())

    def test_missing_source_subtree_cannot_downgrade_linked_policy(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve();main=base/'main';main.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(main),*args],stderr=subprocess.DEVNULL,text=True)
            git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            pkg=main/'pkg';pkg.mkdir();(pkg/'AGENTS.md').write_text('strict subtree rules')
            git('add','.');git('commit','-m','fixture');wt=base/'wt';git('worktree','add','-b','fixture',str(wt))
            registry=base/'settings.json';registry.write_text(json.dumps({'projects':[native(pkg)]}));before=registry.read_bytes()
            (pkg/'AGENTS.md').unlink();pkg.rmdir()
            with self.assertRaisesRegex(ValueError,'unavailable'):onboard(registry,str(wt/'pkg'))
            self.assertEqual(registry.read_bytes(),before)
            self.assertFalse((base/'backups').exists())
            # A genuinely unrelated nested repository must not inherit the outer profile.
            nested=wt/'separate';nested.mkdir();subprocess.check_call(['git','init',str(nested)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertEqual(onboard(registry,str(nested))['project'],str(nested))

    def test_invalid_schema_is_not_quarantined_as_missing(self):
        with tempfile.TemporaryDirectory() as td:
            entry=native(Path(td)/'missing'); entry['integration']['authorities']=['../private']
            with self.assertRaises(ValueError): Runtime({'projects':[entry]})
