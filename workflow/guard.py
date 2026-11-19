#!/usr/bin/env python3
"""Local workflow guard. Engineering evidence, not a security/permission boundary."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.snapshot import snapshot

VERSION = 1
MAX_BYTES = 2_000_000
REVIEW_PREFIX = 'MYCODEX_REVIEW '
DEV = re.compile(r'implement|fix|refactor|develop|add .*(?:function|feature|test)|实现|开发|修复|重构|增加.*(?:功能|测试)|按.*方案.*实施', re.I)
READONLY = re.compile(r'^(?:只读|先只|评估|调研|解释|翻译|translate|explain|read.only|review only)', re.I)
PAUSE = re.compile(r'^(?:停止|暂停|取消|stop|pause|cancel)(?:\b|任务|开发|执行|一下|工作|$)', re.I)
APPROVE = re.compile(r'(?:批准计划|approve plan) ([0-9a-f]{64})')
RESUME = re.compile(r'^(?:恢复(?:任务|开发|执行|工作)?|继续(?:任务|开发|执行|工作)?|resume(?: task| development| work)?)[。.!]?$')
SPAWN_TOOLS = ('spawn_agent', 'Agent', 'functions.spawn_agent', 'collaborationspawn_agent')
MCP_TOOL = 'mcp__quality__quality_info'
WORKFLOW_SKILL = Path('skills/codex-workflow/SKILL.md')
RECEIPT_KEYS = {'kind', 'subject', 'verdict', 'findings', 'closed', 'request'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def safe(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Symlink state/artifact refused')
    return path


def codex_home(directory):
    directory = Path(directory).absolute()
    if directory.parts[-4:] == ('.local', 'state', 'mycodexconfig', 'guard'):
        return directory.parents[3] / '.codex'
    return None


def load(path):
    path = safe(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('State/artifact too large')
    return json.loads(path.read_text())


def atomic(path, value):
    path = safe(path)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    if len(data) > MAX_BYTES:
        raise ValueError('State size limit')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name('.' + path.name + '.' + str(os.getpid()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists(): tmp.unlink()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL,
                                   text=True, timeout=5).strip()


def identity(root):
    root = safe(root).resolve(strict=True)
    checkout = Path(git(root, 'rev-parse', '--show-toplevel')).resolve()
    gd = Path(git(root, 'rev-parse', '--absolute-git-dir')).resolve()
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    linked = gd != common and common / 'worktrees' in gd.parents
    return {'root': str(checkout), 'common': str(common), 'isolated': linked}


class Store:
    def __init__(self, directory, session):
        if not isinstance(session, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', session):
            raise ValueError('Invalid actual session ID')
        self.directory = safe(directory)
        self.key = hashlib.sha256(session.encode()).hexdigest()
        self.path = self.directory / (self.key + '.json')

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = safe(self.directory / (self.key + '.lock'))
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as stream:
            deadline = time.monotonic() + 3
            while True:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except BlockingIOError:
                    if time.monotonic() > deadline: raise ValueError('Guard state busy')
                    time.sleep(.02)
            state = load(self.path) if self.path.exists() else None
            yield state
            if state is not None: atomic(self.path, state)


def context(event, text):
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def deny(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': reason}}


def valid_root(state, path):
    fact = identity(path)
    if fact['common'] != state['common']:
        raise ValueError('Task cannot move to another repository')
    return fact


def plan_current(state):
    plan = state.get('plan')
    if not plan: return False
    try:
        return plan_digest(plan, load(plan['checks_file'])) == plan['hash']
    except (OSError, ValueError): return False


def plan_digest(plan, checks):
    return digest({'text': safe(plan['file']).read_text(), 'checks': checks})


def source_id(state):
    if not state.get('worktree'): raise ValueError('No isolated worktree bound')
    valid_root(state, state['worktree'])
    if not identity(state['worktree'])['isolated']: raise ValueError('Worktree no longer isolated')
    return snapshot(state['worktree'])['id']


def finding_openers(reviews, kind):
    opened = {}
    for review in reviews:
        if review['kind'] == kind:
            if review['verdict'] == 'PASS':
                for finding in review['closed']:
                    opened.pop(finding, None)
            for finding in review['findings']:
                opened[finding] = review['request']
    return opened


def open_findings(reviews, kind):
    return set(finding_openers(reviews, kind))


def pending(state, final=False):
    reasons = []
    if not state.get('skill_read'): reasons.append('read codex-workflow SKILL.md completely')
    if not state.get('plan'): reasons.append('record requirements, plan and check commands with guard plan')
    elif not plan_current(state): reasons.append('plan/check manifest changed; re-record and obtain approval')
    if state.get('approved') != state.get('plan', {}).get('hash') or not state.get('approved'): reasons.append('wait for direct user approval naming the current plan hash')
    if state.get('mcp') != 'native':
        reasons.append('quality MCP missing/unverified; expose and invoke quality_info; report degradation')
    if not state.get('worktree'): reasons.append('bind a real isolated worktree')
    plan = state.get('plan', {})
    reviews = state.get('reviews', [])
    plan_reviews = [r for r in reviews if r['kind'] == 'plan' and r['subject'] == plan.get('hash')]
    if not plan_reviews or plan_reviews[-1]['verdict'] != 'PASS':
        reasons.append('obtain independent plan review bound to current plan hash')
    opened = open_findings(reviews, 'plan')
    if opened: reasons.append('independently close plan findings: ' + ','.join(sorted(opened)))
    if final:
        try: sid = source_id(state)
        except (ValueError, OSError, subprocess.SubprocessError): sid = None
        test = state.get('test')
        if (not sid or not test or test.get('status') != 'complete' or test['source'] != sid
                or test['plan'] != plan.get('hash') or test['exit_code'] != 0):
            reasons.append('run approved checks on current source using guard check')
        if test and test.get('status') == 'complete':
            try:
                for log in test['logs']:
                    path = safe(log['file']); value = load(path)
                    if hashlib.sha256(path.read_bytes()).hexdigest() != log['hash'] or value['source'] != sid or value['exit_code'] != 0:
                        raise ValueError('Changed check log')
            except (ValueError, OSError, KeyError): reasons.append('test log integrity failure')
        current = [r for r in reviews if r['kind'] == 'code' and r['subject'] == sid
                   and r.get('plan') == plan.get('hash') and r.get('run') == (test or {}).get('run')
                   and r.get('worktree') == state.get('worktree')]
        if not current or current[-1]['verdict'] != 'PASS': reasons.append('obtain independent code review on current source')
        opened = open_findings(reviews, 'code')
        if opened: reasons.append('repair, retest and independently close findings: ' + ','.join(sorted(opened)))
    if state.get('review_identity_unavailable'):
        reasons.append('native review dispatch result lacks the actual agent ID required to bind the receipt')
    return reasons


def base_context(state, directory):
    helper = Path(__file__).resolve()
    skill = shlex.quote(str(helper.parents[1] / WORKFLOW_SKILL))
    return ('[MyCodexConfig guard] Read the complete codex-workflow skill at ' + skill + ' before substantive development. '
            'Use guard.py plan/bind/check/status helpers in the installed release; record actual session ID from this hook. '
            'Do not invent approvals, native MCP calls, test results or independent review. '
            'Primary source is read-only. Missing evidence forbids acceptance. '
            'If paused or waiting for user approval, stop and state the missing decision. '
            'First call review-request --kind plan|code, then dispatch a fresh independent reviewer using '
            'the exact task_name returned and include the review nonce in the instructions. '
            'Independent reviewer final line protocol: MYCODEX_REVIEW followed by JSON with request=nonce, kind=plan|code, '
            'subject=current plan hash|source snapshot, verdict=PASS|BLOCKED, findings=[stable IDs], closed=[IDs]. '
            'Reviewer must read actual plan/source/tests and codex-quality-review; never merely echo this protocol. '
            'Approval requires the direct user prompt: approve plan <current plan hash>. '
            'Helper: ' + str(helper) + '; arguments: --state-dir '
            + shlex.quote(str(directory)) + ' --session ' + state['session'] + '; phase: ' + state.get('phase', 'idle'))


def read_only_command(command):
    # A conservative convenience classifier, not arbitrary shell semantic analysis.
    if not isinstance(command, str) or len(command) > 24000: return False
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=';&|<>()')
        lex.whitespace_split = True; tokens = list(lex)
    except ValueError: return False
    if not tokens: return True
    if any(t in ('>', '>>', '<', '<<', '<<<', '&', '(', ')') or '$(' in t or '`' in t for t in tokens): return False
    segments = []; part = []
    for token in tokens + [';']:
        if token in (';', '&&', '||', '|'): segments.append(part); part = []
        else: part.append(token)
    for part in segments:
        if not part: continue
        if part[:2] == ['rtk', 'bypass']: part = part[2:]
        if not part: return False
        cmd = Path(part[0]).name
        if cmd in ('pwd', 'cat', 'head', 'tail', 'ls', 'wc', 'stat', 'which'): continue
        if cmd == 'rg' and not any(t.startswith('--pre') for t in part): continue
        if cmd == 'sed' and not any(t.startswith(('-i', '--in-place')) or 'e' in t or 'w' in t for t in part[1:]): continue
        if cmd == 'git':
            args = part[1:]
            if args[:1] == ['-C']: args = args[2:]
            if any(arg.partition('=')[0] in ('--output', '--ext-diff', '--textconv') for arg in args[1:]):
                return False
            if args and args[0] in ('status', 'diff', 'log', 'show', 'rev-parse', 'rev-list', 'ls-files'): continue
            if args[:2] == ['worktree', 'list']: continue
            if args[:2] == ['worktree', 'add'] and not any(x.startswith('--') and x not in ('--detach',) for x in args[2:]): continue
        # Own helper performs its own validation; do not bless arbitrary Python.
        if cmd.startswith('python') and len(part) >= 3 and Path(part[1]).resolve() == Path(__file__).resolve():
            if any(x in part[2:] for x in ('status', 'plan', 'bind', 'check', 'mcp-missing', 'review-request')): continue
        return False
    return True


def patch_paths(command):
    if not isinstance(command, str): return []
    return re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$', command, re.M) + re.findall(r'^\*\*\* Move to: (.+)$', command, re.M)


def target_paths(tool, inp, cwd):
    if tool == 'apply_patch':
        names = patch_paths(inp.get('patch', inp.get('input', inp.get('command', inp.get('cmd', '')))))
    else:
        names = [inp.get('file_path', inp.get('path', ''))]
    if not names or any(not name for name in names): raise ValueError('Missing actual file target')
    return [safe(Path(cwd) / name).resolve() for name in names]


def planning_paths(paths, root):
    root = Path(root)
    allowed = (root / '.quality', root / 'docs/superpowers/plans')
    return all(any(p != a and a in p.parents for a in allowed) for p in paths)


def receipt(state, event):
    agent = event.get('agent_id')
    if agent not in state.get('agents', {}) or agent == state['session']: return
    dispatched = state['agents'][agent]
    if event.get('turn_id') != dispatched['child_turn']: return
    text = event.get('last_assistant_message') or ''
    lines = text.strip().splitlines()
    if not lines or not lines[-1].startswith(REVIEW_PREFIX): return
    value = json.loads(lines[-1][len(REVIEW_PREFIX):])
    if not isinstance(value, dict) or set(value) != RECEIPT_KEYS: raise ValueError('Invalid reviewer receipt')
    if value['kind'] not in ('plan', 'code') or value['verdict'] not in ('PASS', 'BLOCKED'): raise ValueError('Invalid verdict')
    for k in ('findings', 'closed'):
        if not isinstance(value[k], list) or len(value[k]) > 100 or any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', x) for x in value[k]):
            raise ValueError('Invalid finding IDs')
    if value['verdict'] == 'PASS' and value['findings']: raise ValueError('PASS cannot contain open findings')
    if value['verdict'] == 'BLOCKED' and (not value['findings'] or value['closed']):
        raise ValueError('BLOCKED requires open findings and cannot close findings')
    expected = state.get('plan', {}).get('hash') if value['kind'] == 'plan' else source_id(state)
    if not plan_current(state) or value['subject'] != expected: raise ValueError('Review has stale subject')
    if value['request'] != dispatched['request'] or value['kind'] != dispatched['kind']: raise ValueError('Review request mismatch')
    if dispatched['plan'] != state['plan']['hash']: raise ValueError('Reviewer dispatched on stale plan')
    if value['kind'] == 'code' and dispatched['source'] != expected: raise ValueError('Source changed during review')
    if value['kind'] == 'code':
        test = state.get('test', {})
        if dispatched['worktree'] != state.get('worktree'):
            raise ValueError('Worktree changed during review')
        if (value['verdict'] == 'PASS' and
                (test.get('source') != expected or test.get('exit_code') != 0
                 or test.get('run') != dispatched['run'] or test.get('plan') != dispatched['plan'])):
            raise ValueError('Code PASS requires current successful checks')
    value.update(agent=agent, plan=dispatched['plan'], run=dispatched.get('run'),
                 worktree=dispatched.get('worktree'))
    if any(r['request'] == value['request'] for r in state.get('reviews', [])): return
    opened = finding_openers(state['reviews'], value['kind'])
    if any(finding not in opened or dispatched['openers'].get(finding) != opened[finding]
           for finding in value['closed']):
        raise ValueError('Closure must bind the open finding visible at dispatch')
    if len(state['reviews']) >= 100: raise ValueError('Review history limit')
    state.setdefault('reviews', []).append(value)


def response_object(response):
    if isinstance(response, str):
        try: response = json.loads(response)
        except ValueError: return {}
    return response if isinstance(response, dict) else {}


def child_task_path(state, event, directory):
    home = codex_home(directory)
    transcript = event.get('agent_transcript_path') or event.get('transcript_path')
    if not home or not isinstance(transcript, str): return None
    try:
        root = safe(home / 'sessions').resolve(strict=True)
        candidate = safe(transcript).resolve(strict=True)
        if (root not in candidate.parents or not candidate.is_file()
                or not candidate.name.endswith('-' + event['agent_id'] + '.jsonl')):
            return None
        with candidate.open('rb') as stream:
            limit = 65536
            header = stream.readline(limit + 1)
        if len(header) > limit: return None
        item = json.loads(header)
        meta = item['payload']
        spawn = meta['source']['subagent']['thread_spawn']
        path = meta['agent_path']
        if (item['type'] == 'session_meta' and meta['id'] == event['agent_id']
                and meta['parent_thread_id'] == spawn['parent_thread_id'] == state['session']
                and spawn['depth'] == 1 and spawn['agent_path'] == path
                and re.fullmatch(r'/root/mycodex_review_[0-9a-f]{32}', path)):
            return path
    except (OSError, ValueError, KeyError, TypeError): pass
    return None


def correlate_review(state, agent):
    launches = state.setdefault('launches', {})
    started = state.setdefault('review_starts', {})
    completed = state.setdefault('review_stops', {})
    child = started.get(agent)
    if not child or agent in state['agents']: return
    pairs = [(tool, launch) for tool, launch in launches.items()
             if launch.get('agent') == agent or (child.get('task') and launch.get('task') == child['task'])]
    if len(pairs) != 1: return
    tool, launch = pairs[0]
    launches.pop(tool)
    state.pop('review_identity_unavailable', None)
    state['agents'][agent] = dict(launch['request'], child_turn=started.pop(agent)['turn'])
    if agent in completed:
        receipt(state, completed.pop(agent))


def observe_launch(state, event):
    tool = event.get('tool_use_id')
    launches = state.setdefault('launches', {})
    launch = launches.get(tool)
    if not launch or launch['turn'] != event.get('turn_id'): return
    payload = response_object(event.get('tool_response'))
    if payload.get('error') or payload.get('isError'):
        launches.pop(tool)
        return
    agent = payload.get('agent_id')
    task = payload.get('task_name')
    if isinstance(agent, str) and agent:
        launch['agent'] = agent
        correlate_review(state, agent)
    elif task == '/root/' + launch['request']['task_name']:
        launch['task'] = task
        state['review_identity_unavailable'] = True
        matches = [agent for agent, start in state.get('review_starts', {}).items() if start.get('task') == task]
        if len(matches) == 1: correlate_review(state, matches[0])
    else:
        launches.pop(tool)
        state['review_identity_unavailable'] = True


def quality_info_ok(response):
    payload = response_object(response)
    if payload.get('isError', False) is not False or payload.get('error'): return False
    info = payload.get('structuredContent')
    if not isinstance(info, dict): return False
    return (isinstance(info.get('projects'), list) and isinstance(info.get('resources'), list)
            and isinstance(info.get('project_profiles'), dict)
            and info.get('registration_only_writes') is True and info.get('tools_read_only') is False)


def observe_tool(state, event, directory):
    name = event.get('tool_name', '')
    response = event.get('tool_response')
    text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    if len(text) > MAX_BYTES: text = text[:MAX_BYTES]
    if name == MCP_TOOL:
        state['mcp'] = 'native' if quality_info_ok(response) else 'unverified'
    command = event.get('tool_input', {}).get('command', event.get('tool_input', {}).get('cmd', ''))
    release = Path(__file__).resolve().parents[1]
    relative = WORKFLOW_SKILL
    skill = release / relative
    allowed = [skill, Path.home() / '.codex' / relative]
    home = codex_home(directory)
    if home: allowed.append(home / relative)
    try:
        if (name in ('Bash', 'exec_command', 'functions.exec_command') and isinstance(command, str)
                and any(str(path) in command for path in allowed)
                and skill.read_text().replace('@RUNTIME@', str(release)).strip() in text):
            state['skill_read'] = True
    except OSError: pass


def hook(event, directory):
    name = event.get('hook_event_name')
    session = event.get('session_id')
    store = Store(directory, session)
    if name == 'SessionStart' and not store.path.exists() and event.get('source') == 'startup':
        try: fact = identity(event['cwd'])
        except (ValueError, OSError, subprocess.SubprocessError): return {}
        with store.locked() as existing:
            if existing is None:
                atomic(store.path, {'version': VERSION, 'session': session, 'origin': fact['root'], 'common': fact['common'],
                                    'active': False, 'phase': 'idle', 'agents': {}, 'reviews': [], 'attempts': 0})
    # Existing sessions with no new guard startup stay untouched.
    if not store.path.exists(): return {}
    with store.locked() as state:
        valid_root(state, event['cwd'])
        if name == 'SessionStart': return context(name, base_context(state, directory))
        if name == 'Interrupt':
            state['paused'] = True; state['phase'] = 'paused'
            return {'systemMessage': 'MyCodexConfig: paused; no automatic continuation.'}
        if name == 'UserPromptSubmit':
            prompt = event.get('prompt', '')
            if PAUSE.search(prompt.strip()):
                state['paused'] = True; state['phase'] = 'paused'; return {}
            # Only the exact pending hook continuation is consumed once. It is never approval.
            internal = state.pop('recovery_pending', None)
            if internal and digest(prompt) == internal:
                return context(name, base_context(state, directory))
            if prompt.startswith('[MyCodexConfig recovery]'): return context(name, base_context(state, directory))
            state['turn_readonly'] = bool(READONLY.search(prompt))
            if state.get('paused'):
                if not RESUME.fullmatch(prompt.strip().lower()): return {}
                state['paused'] = False
                state['phase'] = 'planning'
            state['attempts'] = 0
            if DEV.search(prompt) and not state['turn_readonly'] and (state['phase'] == 'verified' or re.search(r'新需求|另一个任务|new task', prompt, re.I)):
                for key in ('plan', 'approved', 'approval_basis', 'test', 'review_request', 'review_identity_unavailable'):
                    state.pop(key, None)
                state.update(reviews=[], agents={}, launches={}, review_starts={}, review_stops={},
                             phase='planning', active=True)
            if not state['active'] and DEV.search(prompt) and not READONLY.search(prompt):
                state.update(active=True, phase='planning')
            approval = APPROVE.fullmatch(prompt.strip().lower())
            if state['active'] and approval and plan_current(state) and approval[1] == state['plan']['hash']:
                state['approval_basis'] = digest(prompt)
                state['approved'] = approval[1]
            return context(name, base_context(state, directory)) if state['active'] else {}
        if not state['active'] or state.get('paused'): return {}
        if name == 'PreToolUse':
            tool = event.get('tool_name', '')
            inp = event.get('tool_input', {})
            if isinstance(inp, str): inp = {'patch': inp}
            if not isinstance(inp, dict): return deny('Malformed tool input')
            command = inp.get('command', inp.get('cmd', ''))
            if tool in SPAWN_TOOLS:
                request = state.get('review_request')
                tool_id = event.get('tool_use_id')
                turn = event.get('turn_id')
                launches = state.setdefault('launches', {})
                if (request and isinstance(tool_id, str) and tool_id and isinstance(turn, str) and turn
                        and tool_id not in launches and len(launches) < 100
                        and inp.get('task_name') == request['task_name'] and inp.get('fork_turns') == 'none'):
                    launches[tool_id] = {'turn': turn, 'request': state.pop('review_request')}
                return {}
            if tool in ('Bash', 'exec_command', 'functions.exec_command') and read_only_command(command): return {}
            effective = inp.get('workdir', inp.get('cwd', event['cwd']))
            paths = None
            if tool in ('apply_patch', 'Edit', 'Write'):
                paths = target_paths(tool, inp, effective)
                valid_root(state, effective)
                if identity(effective)['isolated'] and planning_paths(paths, identity(effective)['root']): return {}
            mutating = tool in ('Bash', 'exec_command', 'functions.exec_command', 'apply_patch', 'Edit', 'Write')
            if mutating:
                reasons = pending(state)
                # Explicit degradation permits implementation; acceptance still requires native MCP.
                if state.get('mcp') == 'missing': reasons = [r for r in reasons if not r.startswith('quality MCP')]
                if reasons: return deny('Workflow prerequisites: ' + '; '.join(reasons))
                root = effective
                if identity(root)['root'] != state['worktree']: return deny('Primary source is read-only; use bound worktree')
                if paths and any(Path(state['worktree']) not in path.parents for path in paths):
                    return deny('Every write target must stay inside the bound worktree')
                state['phase'] = 'implementation'
            return {}
        if name == 'PostToolUse':
            if event.get('tool_name') in SPAWN_TOOLS:
                try: observe_launch(state, event)
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    return {'systemMessage': 'MyCodexConfig: reviewer receipt rejected: ' + str(exc)}
            observe_tool(state, event, directory)
            return {}
        if name == 'SubagentStart':
            agent = event.get('agent_id')
            turn = event.get('turn_id')
            starts = state.setdefault('review_starts', {})
            if (state.get('launches') and isinstance(agent, str) and agent and agent != session
                    and isinstance(turn, str) and turn and len(starts) < 100):
                starts.setdefault(agent, {'turn': turn, 'task': child_task_path(state, event, directory)})
                try: correlate_review(state, agent)
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    return {'systemMessage': 'MyCodexConfig: reviewer receipt rejected: ' + str(exc)}
            return context(name, base_context(state, directory))
        if name == 'SubagentStop':
            try:
                agent = event.get('agent_id')
                if agent in state['agents']:
                    receipt(state, event)
                elif (agent in state.get('review_starts', {})
                      and event.get('turn_id') == state['review_starts'][agent]['turn']
                      and len(state.setdefault('review_stops', {})) < 100):
                    message = event.get('last_assistant_message')
                    line = message.strip().split('\n')[-1] if isinstance(message, str) else ''
                    if line.startswith(REVIEW_PREFIX) and len(line) <= 20000:
                        state['review_stops'][agent] = {'agent_id': agent, 'turn_id': event['turn_id'],
                                                        'last_assistant_message': line}
                        start = state['review_starts'][agent]
                        if not start['task']:
                            start['task'] = child_task_path(state, event, directory)
                        correlate_review(state, agent)
                    elif not line.startswith(REVIEW_PREFIX):
                        state['review_starts'].pop(agent, None)
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                return {'systemMessage': 'MyCodexConfig: reviewer receipt rejected: ' + str(exc)}
            return {}
        if name == 'Stop':
            if state.get('turn_readonly'): return {}
            reasons = pending(state, final=True)
            if not reasons:
                state['phase'] = 'verified'
                return {'systemMessage': '[MyCodexConfig guard] VERIFIED: current plan, checks and independent review evidence.'}
            state['phase'] = 'blocked'
            message = '[MyCodexConfig recovery] Missing: ' + '; '.join(reasons)
            # Waiting for a real human decision or missing MCP cannot be solved by blind retry.
            human = (state.get('approved') != state.get('plan', {}).get('hash') or not state.get('approved')
                     or state.get('mcp') == 'missing' or state.get('review_identity_unavailable'))
            if human or state['attempts'] >= 2:
                return {'systemMessage': message + '; BLOCKED. Do not claim acceptance.'}
            state['attempts'] += 1
            message += '. Complete available steps; do not invent evidence.'
            state['recovery_pending'] = digest(message)
            return {'decision': 'block', 'reason': message}
    return {}


def cli(args):
    store = Store(args.state_dir, args.session)
    if not store.path.exists(): raise ValueError('No startup receipt for this session')
    if args.action == 'check': return run_checks(store)
    with store.locked() as state:
        if args.action != 'status' and (not state['active'] or state.get('paused')):
            raise ValueError('No active, unpaused development task from a user prompt')
        if args.action == 'plan':
            root = valid_root(state, args.root)['root']
            file = safe(Path(root) / args.file); checks_file = safe(Path(root) / args.checks)
            for path in (file, checks_file):
                if Path(root) not in path.resolve().parents: raise ValueError('Plan outside repository')
            text = file.read_text(); checks = load(checks_file)
            if not text.strip() or len(text) > 100000: raise ValueError('Empty/oversized plan')
            if not isinstance(checks, list) or not 1 <= len(checks) <= 12: raise ValueError('Declare 1..12 approved check argv arrays')
            for argv in checks:
                if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x or len(x) > 4000 for x in argv):
                    raise ValueError('Invalid check argv')
            value = digest({'text': text, 'checks': checks})
            old = state.get('plan', {}).get('hash')
            state['plan'] = {'file': str(file), 'checks_file': str(checks_file), 'hash': value}
            if value != old:
                state.pop('approved', None); state.pop('test', None)
            state['phase'] = 'planning'
        elif args.action == 'bind':
            fact = valid_root(state, args.root)
            if not fact['isolated']: raise ValueError('Implementation requires linked Git worktree')
            if state.get('worktree') != fact['root']:
                state.pop('test', None)
            state['worktree'] = fact['root']
        elif args.action == 'review-request':
            if not plan_current(state) or args.kind not in ('plan', 'code'): raise ValueError('Record current plan and review kind first')
            sid = source_id(state) if args.kind == 'code' else None
            nonce = secrets.token_hex(16)
            state['review_request'] = {'request': nonce, 'task_name': 'mycodex_review_' + nonce, 'kind': args.kind,
                'plan': state['plan']['hash'], 'source': sid, 'worktree': state.get('worktree'),
                'run': state.get('test', {}).get('run'), 'openers': finding_openers(state['reviews'], args.kind)}
        elif args.action == 'mcp-missing': state['mcp'] = 'missing'
        return status(state)


def status(state):
    return {'phase': state['phase'], 'plan_hash': state.get('plan', {}).get('hash'),
            'source': source_id(state) if state.get('worktree') else None,
            'missing': pending(state, final=True), 'test': state.get('test'),
            'review_request': state.get('review_request'), 'native_mcp': state.get('mcp') == 'native',
            'attempts': state['attempts']}


def run_checks(store):
    with store.locked() as state:
        if not state['active'] or state.get('paused'):
            raise ValueError('No active, unpaused development task from a user prompt')
        reasons = pending(state)
        if state.get('mcp') == 'missing': reasons = [r for r in reasons if not r.startswith('quality MCP')]
        if reasons: raise ValueError('; '.join(reasons))
        plan = state['plan']
        worktree = state['worktree']
        sid = source_id(state)
        run = secrets.token_hex(16)
        state['test'] = {'status': 'running', 'run': run, 'source': sid, 'plan': plan['hash'],
                         'exit_code': None, 'logs': []}
        state['phase'] = 'checking'

    logs = []
    exit_code = 0
    try:
        checks = load(plan['checks_file'])
        if plan_digest(plan, checks) != plan['hash']:
            raise ValueError('Plan/check manifest changed before execution')
        for index, argv in enumerate(checks):
            with store.locked() as state:
                if state.get('paused') or state.get('test', {}).get('run') != run:
                    raise ValueError('Check run paused or superseded')
            try:
                result = subprocess.run(argv, cwd=worktree, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, timeout=120)
                code, output = result.returncode, result.stdout
            except subprocess.TimeoutExpired as exc:
                code, output = 124, exc.stdout or b''
            log = safe(store.directory / 'logs' / (store.key + '-' + run + '-' + str(index) + '.json'))
            atomic(log, {'argv': argv, 'cwd': worktree, 'source': sid, 'exit_code': code,
                         'output': output.decode('utf-8', errors='replace')})
            logs.append({'file': str(log), 'hash': hashlib.sha256(log.read_bytes()).hexdigest()})
            if code:
                exit_code = code
                break
    except (OSError, ValueError, subprocess.SubprocessError):
        exit_code = 125
        raise
    finally:
        with store.locked() as state:
            test = state.get('test', {})
            if test.get('run') == run:
                test.update(status='complete', exit_code=exit_code or 125, logs=logs)

    with store.locked() as state:
        test = state.get('test', {})
        if test.get('run') != run or state.get('paused') or state.get('worktree') != worktree:
            raise ValueError('Check run paused or superseded')
        if not plan_current(state) or state['plan']['hash'] != plan['hash'] or source_id(state) != sid:
            raise ValueError('Plan or source changed during checks')
        test['exit_code'] = exit_code
        state['phase'] = 'review' if exit_code == 0 else 'repair'
        return status(state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['hook', 'plan', 'bind', 'check', 'status', 'mcp-missing', 'review-request'])
    p.add_argument('--state-dir', required=True); p.add_argument('--session')
    p.add_argument('--kind', choices=['plan', 'code']); p.add_argument('--root'); p.add_argument('--file'); p.add_argument('--checks')
    args = p.parse_args()
    event = {}
    try:
        if args.action == 'hook':
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES: raise ValueError('Hook input too large')
            event = json.loads(raw); result = hook(event, args.state_dir)
        else: result = cli(args)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        if args.action == 'hook':
            result = deny('Guard unavailable: ' + str(exc)) if event.get('hook_event_name') == 'PreToolUse' else {'systemMessage': 'MyCodexConfig guard unavailable; acceptance BLOCKED: ' + str(exc)}
            print(json.dumps(result, ensure_ascii=False)); return 0
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, ensure_ascii=False)); return 2


if __name__ == '__main__': raise SystemExit(main())
