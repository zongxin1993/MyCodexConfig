import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from validate_native import actual_session, verdict, assert_identities, source_hashes, staging_home, activation, session_skill_reads, terminal_verdict


class ValidatorGuards(unittest.TestCase):
    def test_no_requested_session_fallback_or_ambiguous_receipt(self):
        for events in ([], [{'type': 'thread.started'}],
                       [{'type': 'thread.started', 'thread_id': 'x'}] * 2,
                       [{'type': 'thread.started', 'thread_id': 'other'}]):
            with self.subTest(events=events), self.assertRaises(RuntimeError):
                actual_session(events, 'requested')
        self.assertEqual(actual_session([{'type': 'thread.started', 'thread_id': 'x'}], 'x'), 'x')

    def test_prose_pass_cannot_be_acceptance(self):
        for text in ('尚未 PASS，结论 BLOCKED', 'VERDICT: BLOCKED\nPASS', '', 'VERDICT: PASS extra', '说明：VERDICT: BLOCKED'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                verdict({'messages': [text]}, 'PASS')
        verdict({'messages': ['Evidence checked.\nVERDICT: PASS']}, 'PASS')

    def test_malformed_blocked_does_not_enter_plan_repair(self):
        with self.assertRaises(RuntimeError):
            terminal_verdict({'messages':['说明：VERDICT: BLOCKED']})
        self.assertEqual(terminal_verdict({'messages':['Findings.\nVERDICT: BLOCKED']}),'BLOCKED')

    def test_independence_and_repair_are_assertions(self):
        for args in (('w', 'w', 'w'), ('w', 'r', 'replacement'), (None, 'r', None)):
            with self.assertRaises(RuntimeError): assert_identities(*args)
        assert_identities('w', 'r', 'w')

    def test_new_test_and_deleted_source_change_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'a.py').write_text('a')
            before = source_hashes(root)
            (root/'new.py').write_text('b'); self.assertNotEqual(before, source_hashes(root))
            (root/'new.py').unlink(); (root/'a.py').unlink()
            self.assertNotEqual(before, source_hashes(root))

    def test_active_home_refused(self):
        with self.assertRaises(ValueError): staging_home(Path.home())

    def test_activation_requires_observed_actions_not_model_claims(self):
        with self.assertRaises(RuntimeError):
            activation({'messages':['I used codex-workflow and quality_info']}, True)
        actual={'skill_read_receipts':[{'call_id':'observed'}], 'actions':[{'type':'command_execution','status':'completed','exit_code':0,
                            'command':'cat /skills/codex-workflow/SKILL.md'},
                           {'type':'mcp_tool_call','status':'completed','server':'quality','tool':'quality_info'}]}
        self.assertTrue(activation(actual,True)['session_native_mcp_observed'])
        with self.assertRaises(RuntimeError): activation(actual,False)
        activation({'actions':[]},False)

    def test_skill_read_requires_paired_full_installed_source(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);session='11111111-1111-1111-1111-111111111111'
            directory=home/'.codex/sessions';directory.mkdir(parents=True)
            skill=home/'.codex/skills/codex-workflow/SKILL.md';skill.parent.mkdir(parents=True)
            text='# Codex engineering workflow\nFull installed instructions.\n';skill.write_text(text)
            path=directory/('rollout-'+session+'.jsonl')
            call={'type':'response_item','payload':{'type':'function_call','name':'exec_command',
                  'arguments':json.dumps({'cmd':'cat '+str(skill)}),'call_id':'actual'}}
            output={'type':'response_item','payload':{'type':'function_call_output','call_id':'other','output':text}}
            def save():path.write_text(json.dumps(call)+'\n'+json.dumps(output)+'\n')
            save();self.assertEqual(session_skill_reads(home,session),[])
            output['payload']['call_id']='actual';output['payload']['output']='# Codex engineering workflow'
            save();self.assertEqual(session_skill_reads(home,session),[])
            output['payload']['output']=text;call['payload']['arguments']=json.dumps({'cmd':'cat /wrong/codex-workflow/SKILL.md'})
            save();self.assertEqual(session_skill_reads(home,session),[])
            call['payload']['arguments']=json.dumps({'cmd':"printf '%s' '# Codex engineering workflow' # cat "+str(skill)})
            save();self.assertEqual(session_skill_reads(home,session),[])
            call['payload']['arguments']=json.dumps({'cmd':'cat '+str(skill)+'; pwd'})
            save();self.assertEqual(session_skill_reads(home,session)[0]['call_id'],'actual')

    def test_readonly_phase_rejects_actual_new_file_even_with_green_model(self):
        import subprocess
        from unittest.mock import patch
        import validate_native as shared
        with tempfile.TemporaryDirectory() as td:
            base=Path(td).resolve(); home=base/'stage';(home/'.codex').mkdir(parents=True)
            root=base/'source';root.mkdir(); evidence=base/'evidence';evidence.mkdir()
            def run(argv, **kwargs):
                (root/'unexpected.py').write_text('mutation')
                kwargs['stdout'].write('{"type":"thread.started","thread_id":"actual"}\n')
                return subprocess.CompletedProcess(argv,0)
            with patch.object(shared.subprocess,'run',side_effect=run):
                with self.assertRaisesRegex(RuntimeError,'modified source'):
                    shared.call(home,root,evidence,'readonly','fixture',readonly=True)
