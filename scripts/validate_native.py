#!/usr/bin/env python3
"""Isolated real Codex workflow fixture; raw evidence stays outside this repository."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()


def call(home, root, evidence, name, prompt, session=None, readonly=False):
    env = os.environ.copy(); env['CODEX_HOME'] = str(home / '.codex')
    argv = ['codex', 'exec', '-C', str(root), '-s', 'read-only' if readonly else 'workspace-write',
            '-c', 'model_reasoning_effort="low"', '-c', 'mcp_servers.context7.enabled=false']
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
    threads = [e['thread_id'] for e in events if e.get('type') == 'thread.started']
    messages = [e['item'].get('text', '') for e in events if e.get('item', {}).get('type') == 'agent_message']
    errors = [e for e in events if e.get('type') in ('error', 'turn.failed')]
    result_value = {'session': threads[0] if threads else session, 'exit_code': result.returncode,
                    'messages': messages, 'errors': errors}
    (evidence / (name + '.result.json')).write_text(json.dumps(result_value, ensure_ascii=False, indent=2))
    if result.returncode or errors: raise RuntimeError(name + ' failed; inspect private evidence')
    print(name + ' completed: ' + str(result_value['session']), flush=True)
    return result_value


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--home', required=True, type=Path); p.add_argument('--fixture', required=True, type=Path)
    args = p.parse_args(); base = args.fixture.resolve(); base.mkdir(mode=0o700)
    primary = base / 'primary'; primary.mkdir(); evidence = base / 'evidence'; evidence.mkdir(mode=0o700)
    git(primary, 'init'); git(primary, 'config', 'user.name', 'Fixture'); git(primary, 'config', 'user.email', 'fixture@example.invalid')
    (primary / 'AGENTS.md').write_text('Validation fixture. Repository-native governance. Keep requirements/plan/review in task context, not new governance files. Implement only in linked worktree; primary checkout is read-only. Allowed code: ids.py and tests/test_ids.py. Run python3 -m unittest discover -s tests -v. No commits/push/network/dependencies.\n')
    (primary / 'README.md').write_text('Isolated Codex validation fixture; no real product data.\n')
    (primary / 'ids.py').write_text('def normalize_ids(items):\n    raise NotImplementedError\n')
    git(primary, 'add', '.'); git(primary, 'commit', '-m', 'fixture baseline')
    worktree = base / 'worktree'; git(primary, 'worktree', 'add', '-b', 'fixture/task', str(worktree))
    baseline = git(primary, 'rev-parse', 'HEAD')
    prefix = ('This is an isolated validation fixture, not a real user project. All scripted approvals below are fixture-only. '
              'Use installed codex-workflow and relevant Codex-only skills, quality MCP and native tools. '
              'Never access OpenCode or unrelated directories. Respect AGENTS.md. Respond in Chinese with stage/status. ')
    first = call(args.home, worktree, evidence, '01-clarification', prefix + '需求：实现 normalize_ids 去重。先用 GrillMe/grilling 思路提出一个最关键的澄清问题，不写文件、不实施。', readonly=True)
    worker = first['session']
    second = call(args.home, worktree, evidence, '02-plan', prefix + '测试操作者的澄清答复：输入是有限 list[int]；仅接受非负整数，bool 也必须拒绝。去重保持首次出现顺序，不修改输入。非法元素抛 ValueError；非法容器抛 TypeError；空列表返回空列表。REQ-1 输入和验证，REQ-2 稳定去重和无副作用。需求已由测试操作者确认（仅 fixture）。现在写具体计划、验收案例和测试命令到回复中，等待计划批准。不要改文件。', session=worker, readonly=True)
    if git(worktree, 'status', '--porcelain'): raise RuntimeError('Clarification/planning modified source')
    third = call(args.home, worktree, evidence, '03-implementation', prefix + '测试操作者批准上一轮计划，仅用于此 fixture。实施并测试。使用 rg 定位，再读取当前源码；确认当前是 linked worktree。保留测试原始结果，不写治理文件。完成后等待独立审计，不提交。', session=worker)
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=worktree, capture_output=True, text=True)
    (evidence / 'implementation-tests.log').write_text(test.stdout + test.stderr)
    if test.returncode: raise RuntimeError('Initial implementation did not pass tests')
    before_mutation = (worktree / 'ids.py').read_text()
    (evidence / 'implementation-before-mutation.py').write_text(before_mutation)
    # A declared mutation tests reviewer detection and the same-worker repair loop.
    (worktree / 'ids.py').write_text('def normalize_ids(items):\n    return list(dict.fromkeys(items))\n')
    review_prompt = prefix + ('Independent READ-ONLY review of current ids.py and tests/test_ids.py against these approved requirements: '
        'list container only; nonnegative int elements only; reject bool and invalid element with ValueError; bad container TypeError; '
        'stable dedup; no input mutation; empty returns []. The validation harness deliberately replaced ids.py after implementation '
        'with an unchecked dedup mutant; examine current source and tests, do not trust earlier PASS. '
        'Load codex-quality-review and quality MCP BMAD quick resources. Return BLOCKED/PASS, finding IDs, exact lines, '
        'trigger, expected/actual, severity, impact, urgency, repair value/cost/regression risk. No edits. No acceptance artifact creation.')
    source_before_review = (worktree / 'ids.py').read_bytes()
    review = call(args.home, worktree, evidence, '04-independent-review', review_prompt, readonly=True)
    if (worktree / 'ids.py').read_bytes() != source_before_review: raise RuntimeError('Reviewer modified source')
    if not any('BLOCKED' in s for s in review['messages']): raise RuntimeError('Reviewer did not block known invalid mutant')
    repair = call(args.home, worktree, evidence, '05-same-worker-repair', prefix + '独立审计回报如下（当前源码已被验证操作者故意植入缺陷，用于验证修复环路）：\n' + '\n'.join(review['messages']) + '\n请核对实际代码，修复真实问题，保留问题 ID，增加或运行能复现问题的测试，复验后返回待独立复审。不要提交。', session=worker)
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=worktree, capture_output=True, text=True)
    (evidence / 'repair-tests.log').write_text(test.stdout + test.stderr)
    if test.returncode: raise RuntimeError('Repair tests failed')
    rereview = call(args.home, worktree, evidence, '06-independent-rereview', prefix + '重新独立只读复审当前修复后的源码、测试和上一轮问题。读取实际源码并核对差异，判断是否达到上述已批准需求。报告每个原问题 ID 的关闭依据和未验证事项，给出 PASS 或 BLOCKED。不要编辑。', session=review['session'], readonly=True)
    if not any('PASS' in s for s in rereview['messages']): raise RuntimeError('Re-review did not pass')
    if git(primary, 'status', '--porcelain') or git(primary, 'rev-parse', 'HEAD') != baseline:
        raise RuntimeError('Primary checkout changed')
    summary = {'status': 'PASS', 'fixture_only': True, 'model_reasoning_effort': 'low', 'primary_unchanged': True,
               'baseline': baseline, 'same_worker_repaired': worker == repair['session'],
               'independent_reviewer': worker != review['session'], 'known_mutant_blocked': True,
               'repair_tests_exit': test.returncode, 'raw_evidence': str(evidence),
               'worker': worker, 'reviewer': review['session']}
    (evidence / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
