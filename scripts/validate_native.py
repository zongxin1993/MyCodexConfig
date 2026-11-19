#!/usr/bin/env python3
"""Isolated real Codex workflow fixture; raw evidence stays outside this repository."""
import argparse
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import subprocess
import sys


FIXTURE_REQUIREMENTS = (
    'REQ-1: only exact built-in list containers and exact nonnegative built-in int elements are accepted; '
    'reject list/int subclasses and bool. Bad container raises TypeError; bad element raises ValueError. '
    'REQ-2: stable dedup preserving first occurrence, return a new list, no input mutation on success/error; empty returns [].'
)

def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()


def source_hashes(root):
    """Hash fixture source, including new files; exclude generated build/cache data."""
    if any(p.is_symlink() for p in root.rglob('*')
           if not any(x in ('.git', 'target', '__pycache__') for x in p.relative_to(root).parts)):
        raise ValueError('Symlink fixture source refused')
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()
            and not any(x in ('.git', 'target', '__pycache__') for x in p.relative_to(root).parts)}


def staging_home(home):
    stage = (home / '.codex').resolve(strict=True)
    active = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()
    if stage in (active, (Path.home() / '.codex').resolve()): raise ValueError('Refuse active Codex home')
    for name in ('auth.json', 'config.toml'):
        candidate = home / '.codex' / name
        if candidate.is_symlink(): raise ValueError('Refuse shared staging file symlink')
        for active_root in (active, Path.home() / '.codex'):
            original = active_root / name
            if candidate.exists() and original.exists() and candidate.samefile(original):
                raise ValueError('Refuse shared staging file inode')
    return home.resolve(strict=True)


def actual_session(events, requested=None):
    ids = [e.get('thread_id') for e in events if e.get('type') == 'thread.started']
    if len(ids) != 1 or not isinstance(ids[0], str) or not ids[0].strip():
        raise RuntimeError('Missing or ambiguous actual thread.started receipt')
    if requested and ids[0] != requested: raise RuntimeError('Resume returned a different actual session')
    return ids[0]


def terminal_verdict(result):
    lines = '\n'.join(result['messages']).strip().splitlines()
    if not lines or lines[-1] not in ('VERDICT: PASS', 'VERDICT: BLOCKED'):
        raise RuntimeError('Malformed independent verdict; inspect private evidence')
    return lines[-1].removeprefix('VERDICT: ')


def verdict(result, expected):
    if terminal_verdict(result) != expected:
        raise RuntimeError('Unexpected independent verdict; inspect private evidence')


def session_skill_reads(home, session):
    """CLI event summaries can omit an initial exec; inspect this test session's paired receipts."""
    if not re.fullmatch(r'[0-9a-f-]{36}', session): return []
    matches = list((home / '.codex/sessions').rglob('*-' + session + '.jsonl'))
    if len(matches) != 1 or matches[0].is_symlink(): return []
    skill = home / '.codex/skills/codex-workflow/SKILL.md'
    if not skill.is_file() or skill.is_symlink(): return []
    content = skill.read_text().strip()
    if not content: return []
    calls = {}; reads = []
    for line in matches[0].read_text().splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        value = event.get('payload', {})
        if event.get('type') != 'response_item': continue
        if value.get('type') == 'function_call' and value.get('name') in ('exec_command', 'functions.exec_command'):
            try: args = json.loads(value.get('arguments', '{}'))
            except ValueError: continue
            if not isinstance(args, dict): continue
            command = args.get('cmd', '')
            if not isinstance(command, str): continue
            try:
                lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
                lexer.whitespace_split = True
                tokens = list(lexer)
            except ValueError: continue
            # Accept an actual cat segment reading the exact staged skill path.
            segments = []; segment = []
            for token in tokens + [';']:
                if token in (';', '&&', '||', '|', '&'):
                    segments.append(segment); segment = []
                else: segment.append(token)
            if any(part and part[0] == 'cat' and str(skill) in part[1:] for part in segments):
                calls[value.get('call_id')] = command
        if value.get('type') == 'function_call_output' and value.get('call_id') in calls:
            output = str(value.get('output', ''))
            if content in output:
                reads.append({'call_id': value['call_id'], 'command': calls[value['call_id']],
                              'skill_sha256': hashlib.sha256(skill.read_bytes()).hexdigest(),
                              'output_sha256': hashlib.sha256(output.encode()).hexdigest()})
    return reads


def activation(result, expected):
    # A paired source-read receipt is required; prose and command names alone are insufficient.
    loaded = bool(result.get('skill_read_receipts'))
    native = any(a.get('type') == 'mcp_tool_call' and a.get('server') == 'quality'
                 and a.get('tool') == 'quality_info' and a.get('status') == 'completed'
                 and not a.get('error') for a in result.get('actions', []))
    if expected and not (loaded and native):
        raise RuntimeError('Implicit skill/native MCP activation unverified in session events')
    if not expected and (loaded or native):
        raise RuntimeError('Bounded simple request unexpectedly activated engineering workflow')
    return {'skill_read_observed': loaded, 'session_native_mcp_observed': native,
            'scope': 'CLI session only; Desktop unverified'}


def assert_identities(worker, reviewer, repair):
    if not worker or not reviewer or worker == reviewer: raise RuntimeError('Reviewer is not independent')
    if repair != worker: raise RuntimeError('Repair did not resume the same worker')


def call(home, root, evidence, name, prompt, session=None, readonly=False, isolated_auth=True):
    if not isolated_auth: raise ValueError('Real model validation requires isolated file auth')
    home = staging_home(home)
    before = source_hashes(root) if readonly else None
    env = os.environ.copy(); env['CODEX_HOME'] = str(home / '.codex')
    if isolated_auth:
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY'):
            env.pop(key, None)
    argv = ['codex', 'exec', '-C', str(root), '-s', 'read-only' if readonly else 'workspace-write',
            '-c', 'model_reasoning_effort="low"', '-c', 'mcp_servers.context7.enabled=false']
    if isolated_auth: argv += ['-c', 'cli_auth_credentials_store="file"']
    if session: argv += ['resume', '--json', session, '-']
    else: argv += ['--trust', '--json', '-']
    path = evidence / (name + '.jsonl')
    with path.open('w') as out:
        os.chmod(path, 0o600)
        result = subprocess.run(argv, input=prompt, text=True, stdout=out, stderr=subprocess.STDOUT, env=env, timeout=900)
    events = []
    for line in path.read_text().splitlines():
        try: events.append(json.loads(line))
        except ValueError: pass
    session_id = actual_session(events, session)
    messages = [e['item'].get('text', '') for e in events if e.get('item', {}).get('type') == 'agent_message']
    errors = [e for e in events if e.get('type') in ('error', 'turn.failed')]
    result_value = {'session': session_id, 'exit_code': result.returncode,
                    'messages': messages, 'errors': errors,
                    'actions': [e['item'] for e in events if e.get('type') == 'item.completed'
                                and e.get('item', {}).get('type') not in ('agent_message', 'reasoning')],
                    'source_hashes': source_hashes(root),
                    'skill_read_receipts': session_skill_reads(home, session_id)}
    (evidence / (name + '.result.json')).write_text(json.dumps(result_value, ensure_ascii=False, indent=2))
    if readonly and before != source_hashes(root): raise RuntimeError('Read-only phase modified source')
    if result.returncode or errors: raise RuntimeError(name + ' failed; inspect private evidence')
    print(name + ' completed: ' + str(result_value['session']), flush=True)
    return result_value


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--home', required=True, type=Path); p.add_argument('--fixture', required=True, type=Path); p.add_argument('--explicit-workflow', action='store_true', help='Test explicitly requested workflow integration only; does not certify implicit activation')
    args = p.parse_args(); args.home = staging_home(args.home); base = args.fixture.resolve(); base.mkdir(mode=0o700)
    primary = base / 'primary'; primary.mkdir(); evidence = base / 'evidence'; evidence.mkdir(mode=0o700)
    git(primary, 'init'); git(primary, 'config', 'user.name', 'Fixture'); git(primary, 'config', 'user.email', 'fixture@example.invalid')
    (primary / 'AGENTS.md').write_text('Validation fixture. Repository-native governance. Keep requirements/plan/review in task context, not new governance files. Implement only in linked worktree; primary checkout is read-only. Allowed code: ids.py and tests/test_ids.py. Run python3 -m unittest discover -s tests -v. No commits/push/network/dependencies.\n')
    (primary / 'README.md').write_text('Isolated Codex validation fixture; no real product data.\n')
    (primary / 'ids.py').write_text('def normalize_ids(items):\n    raise NotImplementedError\n')
    git(primary, 'add', '.'); git(primary, 'commit', '-m', 'fixture baseline')
    worktree = base / 'worktree'; git(primary, 'worktree', 'add', '-b', 'fixture/task', str(worktree))
    baseline = git(primary, 'rev-parse', 'HEAD'); original = source_hashes(primary)
    prefix = ('This is an isolated validation fixture, not a real user project. All scripted approvals below are fixture-only. '
              ''
              'Never access OpenCode or unrelated directories. Respect AGENTS.md. Respond in Chinese with stage/status. ')
    if args.explicit_workflow: prefix += 'Use codex-workflow and its session-native quality preflight. '
    first = call(args.home, worktree, evidence, '01-clarification', prefix + '帮我完成 normalize_ids 去重功能。开始前先和我确认一个最关键的需求边界，暂不修改文件。', readonly=True)
    observed = activation(first, True)
    negative = call(args.home, worktree, evidence, '01b-simple-negative', '把 hello 翻译成中文，只回答译文。', readonly=True)
    activation(negative, False)
    worker = first['session']
    second = call(args.home, worktree, evidence, '02-plan', prefix + FIXTURE_REQUIREMENTS + ' 测试操作者已确认这些合成需求，仅fixture。给出具体计划、验收案例和测试命令到回复中，等待批准，不改文件。', session=worker, readonly=True)
    if git(worktree, 'status', '--porcelain'): raise RuntimeError('Clarification/planning modified source')
    plan_review = call(args.home, worktree, evidence, '02b-independent-plan-review', prefix + FIXTURE_REQUIREMENTS + '独立只读审查以下需求和实施计划，检查边界、验收案例及验证命令是否充分。不要实施或修改文件。最后一行必须是 VERDICT: PASS 或 VERDICT: BLOCKED。\n' + '\n'.join(second['messages']), readonly=True)
    if plan_review['session'] == worker: raise RuntimeError('Plan reviewer is not independent')
    plan_text = '\n'.join(plan_review['messages']).strip()
    if terminal_verdict(plan_review) == 'BLOCKED':
        second = call(args.home, worktree, evidence, '02c-plan-repair', prefix +
            '独立计划审查回报：\n' + plan_text +
            '\n测试操作者已确认的合成需求：' + FIXTURE_REQUIREMENTS + '补齐验收案例，修订计划，不实施。', session=worker, readonly=True)
        plan_review = call(args.home, worktree, evidence, '02d-plan-rereview', prefix +
            FIXTURE_REQUIREMENTS + '独立复审修订计划和原问题关闭依据，不改文件或测试；'
            '最后一行必须是 VERDICT: PASS 或 VERDICT: BLOCKED。\n' + '\n'.join(second['messages']),
            session=plan_review['session'], readonly=True)
    verdict(plan_review, 'PASS')
    third = call(args.home, worktree, evidence, '03-implementation', prefix + '测试操作者批准上一轮计划，仅用于此 fixture。实施并测试。使用 rg 定位，再读取当前源码；确认当前是 linked worktree。保留测试原始结果，不写治理文件。完成后等待独立审计，不提交。', session=worker)
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=worktree, capture_output=True, text=True)
    (evidence / 'implementation-tests.log').write_text(test.stdout + test.stderr)
    if test.returncode: raise RuntimeError('Initial implementation did not pass tests')
    before_mutation = (worktree / 'ids.py').read_text()
    (evidence / 'implementation-before-mutation.py').write_text(before_mutation)
    # A declared mutation tests reviewer detection and the same-worker repair loop.
    (worktree / 'ids.py').write_text('def normalize_ids(items):\n    return list(dict.fromkeys(items))\n')
    review_prompt = prefix + ('Independent READ-ONLY review of current ids.py and tests/test_ids.py against these approved requirements: '
        + FIXTURE_REQUIREMENTS + ' Examine current source and tests, do not trust earlier PASS. '
        'Load codex-quality-review and quality MCP BMAD quick resources. Last line must be VERDICT: BLOCKED or VERDICT: PASS. Return finding IDs, exact lines, '
        'trigger, expected/actual, severity, impact, urgency, repair value/cost/regression risk. No edits. No acceptance artifact creation.')
    source_before_review = (worktree / 'ids.py').read_bytes()
    review = call(args.home, worktree, evidence, '04-independent-review', review_prompt, readonly=True)
    if (worktree / 'ids.py').read_bytes() != source_before_review: raise RuntimeError('Reviewer modified source')
    if review['session'] in (worker, plan_review['session']): raise RuntimeError('Code review is not independent')
    verdict(review, 'BLOCKED')
    repair = call(args.home, worktree, evidence, '05-same-worker-repair', prefix + '独立审计回报如下（当前源码已被验证操作者故意植入缺陷，用于验证修复环路）：\n' + '\n'.join(review['messages']) + '\n请核对实际代码，修复真实问题，保留问题 ID，增加或运行能复现问题的测试，复验后返回待独立复审。不要提交。', session=worker)
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=worktree, capture_output=True, text=True)
    (evidence / 'repair-tests.log').write_text(test.stdout + test.stderr)
    if test.returncode: raise RuntimeError('Repair tests failed')
    receipt = {'source_hashes': source_hashes(worktree), 'test_exit': test.returncode, 'log': str(evidence / 'repair-tests.log')}
    (evidence / 'repair-checks.json').write_text(json.dumps(receipt, indent=2))
    rereview = call(args.home, worktree, evidence, '06-independent-rereview', prefix + FIXTURE_REQUIREMENTS + f'原始验证证据：{evidence / "repair-checks.json"} 与 {evidence / "repair-tests.log"}。读取并核对当前源码与摘要，区分外部验证和自身检查；不要在只读审计运行会产生文件的测试。' + '重新独立只读复审当前修复后的源码、测试和上一轮问题。读取实际源码并核对差异，判断是否达到上述已批准需求。报告每个原问题 ID 的关闭依据和未验证事项，最后一行必须是 VERDICT: PASS 或 VERDICT: BLOCKED。不要编辑。', session=review['session'], readonly=True)
    verdict(rereview, 'PASS')
    assert_identities(worker, review['session'], repair['session'])
    if git(primary, 'status', '--porcelain') or git(primary, 'rev-parse', 'HEAD') != baseline or source_hashes(primary) != original:
        raise RuntimeError('Primary checkout changed')
    summary = {'status': 'PASS', 'fixture_only': True, 'model_reasoning_effort': 'low', 'primary_unchanged': True,
               'baseline': baseline, 'activation_evidence': observed, 'invocation_mode': 'explicit' if args.explicit_workflow else 'implicit', 'desktop_acceptance': 'UNVERIFIED', 'same_worker_repaired': worker == repair['session'],
               'independent_reviewer': worker != review['session'], 'known_mutant_blocked': True,
               'repair_tests_exit': test.returncode, 'raw_evidence': str(evidence),
               'plan_reviewer': plan_review['session'], 'worker': worker, 'reviewer': review['session']}
    (evidence / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
