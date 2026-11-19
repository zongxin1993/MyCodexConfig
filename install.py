#!/usr/bin/env python3
"""Backup-first Codex-only installer. No OpenCode or authentication writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import uuid
try:
    import tomllib
except ImportError:
    raise SystemExit("MyCodexConfig requires Python 3.11 or newer")

ROOT = Path(__file__).resolve().parent
START = '# BEGIN MyCodexConfig managed'
END = '# END MyCodexConfig managed'
MARKER = 'Managed-By: MyCodexConfig'
DISABLED = ('quality-planning', 'quality-review', 'local-execution', 'ast-grep', 'rust-diagnostics')
GUARD_STATUS = 'MyCodexConfig workflow guard'
GUARD_EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
                'SubagentStart', 'SubagentStop', 'Stop', 'Interrupt')
CONTEXT_EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'SubagentStart')


def sha(data): return hashlib.sha256(data).hexdigest()


def safe(path):
    for p in (path, *path.parents):
        if p.is_symlink(): raise ValueError('Refuse symlink destination: ' + str(p))


def atomic(path, data):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.mycodex-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), 0o600); out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def managed(text, body):
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError('Ambiguous managed block')
    if START in text:
        a, b = text.index(START), text.index(END) + len(END)
        if b < a: raise ValueError('Invalid managed block order')
        text = text[:a] + text[b:]
    return text.rstrip() + '\n\n' + START + '\n' + body.rstrip() + '\n' + END + '\n'


def foreign_config(text, home):
    """Retain host-added tables even when Codex inserted them inside our markers."""
    if START not in text:
        return text
    managed(text, '')  # Validate marker count/order before slicing.
    a, b = text.index(START), text.index(END)
    body = text[a + len(START):b]
    # A header-looking line inside an unfinished multiline value is not a boundary.
    sections = []
    current = ''
    for line in body.splitlines(keepends=True):
        if re.match(r'^\s*\[', line) and current.strip():
            try:
                tomllib.loads(current)
            except tomllib.TOMLDecodeError:
                pass
            else:
                sections.append(current)
                current = ''
        current += line
    sections.append(current)
    kept = []
    for section in sections:
        if not section.strip():
            continue
        data = tomllib.loads(section)
        owned = (set(data) == {'mcp_servers'} and
                 set(data['mcp_servers']).issubset({'quality', 'context7'}))
        if owned:
            server = next(iter(data['mcp_servers']), None)
            allowed = {'command', 'args', 'cwd', 'startup_timeout_sec', 'tool_timeout_sec', 'enabled_tools'} if server == 'quality' else {'url', 'startup_timeout_sec', 'tool_timeout_sec', 'enabled_tools'}
            if server and not set(data['mcp_servers'][server]).issubset(allowed):
                raise ValueError('Ambiguous managed MCP extension: ' + server)
        if set(data) == {'skills'} and set(data['skills']) == {'config'}:
            entries = data['skills']['config']
            owned_paths = {str(home / '.agents/skills' / name / 'SKILL.md') for name in DISABLED}
            owned = (isinstance(entries, list) and len(entries) == 1 and
                     entries[0].get('path') in owned_paths)
        if not owned:
            if data and not section.lstrip().startswith('['):
                raise ValueError('Ambiguous root settings inside managed config block')
            kept.append(section)
    return text[:a].rstrip() + '\n\n' + ''.join(kept) + text[b + len(END):]


def payload(ast_grep=None):
    paths = [ROOT / 'tools.py']
    for directory in ('workflow', 'schemas', 'examples', 'resources', 'skills'):
        paths.extend(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and not any(part in ('__pycache__', 'target', '.private', '.git') for part in p.relative_to(ROOT).parts) and p.suffix != '.pyc')
    result = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(paths)}
    if ast_grep is not None:
        binary = Path(ast_grep).resolve(strict=True)
        if not binary.is_file() or not os.access(binary, os.X_OK): raise ValueError('ast-grep must be executable')
        result['bin/ast-grep'] = binary.read_bytes()
    return dict(sorted(result.items()))


def config_block(home, release, python, context7):
    quote = json.dumps
    lines = ['[mcp_servers.quality]', 'command = ' + quote(python),
             'args = ' + quote(['-m', 'workflow.server', '--settings', str(home / '.config/mycodexconfig/settings.json')]),
             'cwd = ' + quote(str(release)), 'startup_timeout_sec = 20', 'tool_timeout_sec = 60',
             'enabled_tools = ["quality_info", "quality_resource", "quality_onboard", "quality_prepare", "quality_gate"]']
    if context7:
        lines += ['', '[mcp_servers.context7]', 'url = "https://mcp.context7.com/mcp/oauth"',
                  'startup_timeout_sec = 30', 'tool_timeout_sec = 60',
                  'enabled_tools = ["resolve-library-id", "query-docs"]']
    for name in DISABLED:
        lines += ['', '[[skills.config]]', 'path = ' + quote(str(home / '.agents/skills' / name / 'SKILL.md')), 'enabled = false']
    return '\n'.join(lines)


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate hooks.json key: ' + key)
        result[key] = value
    return result


def merge_hooks(raw, home, release, python, enabled):
    document = json.loads(raw, object_pairs_hook=unique_json_object) if raw is not None else {}
    if not isinstance(document, dict) or not isinstance(document.get('hooks', {}), dict):
        raise ValueError('Invalid hooks.json: expected an object containing a hooks object')
    original = document.get('hooks', {})
    merged = {}
    state_dir = str(home / '.local/state/mycodexconfig/guard')
    command = shlex.join([python, str(release / 'workflow/guard.py'), 'hook', '--state-dir', state_dir])
    guards = {}
    had_guard = False
    trust_changed = False
    if enabled is not False:
        for event in GUARD_EVENTS:
            handler = {'type': 'command', 'command': command, 'statusMessage': GUARD_STATUS,
                       'timeout': 3 if event == 'Interrupt' else 10}
            if event in CONTEXT_EVENTS:
                handler['additionalContextLimit'] = 1200
            guards[event] = handler
    for event, groups in original.items():
        if not isinstance(groups, list):
            raise ValueError('Invalid hooks.json groups: ' + event)
        kept_groups = []
        for group in groups:
            if (not isinstance(group, dict) or not isinstance(group.get('hooks'), list)
                    or any(not isinstance(handler, dict) or not isinstance(handler.get('type'), str)
                           for handler in group['hooks'])):
                raise ValueError('Invalid hooks.json group: ' + event)
            if group.get('matcher') is not None and not isinstance(group['matcher'], str):
                raise ValueError('Invalid hooks.json matcher: ' + event)
            owned = [handler for handler in group['hooks'] if handler.get('statusMessage') == GUARD_STATUS]
            if not owned:
                kept_groups.append(group)
                continue
            if (len(owned) != 1 or len(group['hooks']) != 1 or set(group) != {'hooks'}
                    or not is_guard_handler(owned[0], release.parent, state_dir)):
                raise ValueError('Foreign workflow guard hook collision: ' + event)
            had_guard = True
            handler = guards.pop(event, None)
            if handler is not None and handler['command'] != owned[0]['command']:
                trust_changed = True
            kept_groups.append({'hooks': [handler]} if handler is not None else None)
        while kept_groups and kept_groups[-1] is None:
            kept_groups.pop()
        if kept_groups or not groups:
            # Hook trust IDs include the matcher-group index. Preserve later foreign IDs.
            merged[event] = [group if group is not None else {'hooks': []} for group in kept_groups]
    active = enabled is True or (enabled is None and had_guard)
    if active:
        for event, handler in guards.items():
            merged.setdefault(event, []).append({'hooks': [handler]})
    foreign_stop = active and any(
        handler.get('statusMessage') != GUARD_STATUS
        for group in merged.get('Stop', []) for handler in group['hooks'])
    if merged != original:
        document['hooks'] = merged
        raw = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
    return raw, active, foreign_stop, trust_changed


def is_guard_handler(handler, releases, state_dir):
    command = handler.get('command')
    if handler.get('type') != 'command' or not isinstance(command, str):
        return False
    parts = shlex.split(command)
    if len(parts) != 5 or parts[2:] != ['hook', '--state-dir', state_dir]:
        return False
    script = Path(parts[1])
    return (Path(parts[0]).is_absolute() and script.is_absolute() and len(script.parents) >= 3
            and script.parts[-2:] == ('workflow', 'guard.py')
            and script.parents[2] == releases)


def install(home, context7=True, ast_grep=None, workflow_hooks=None):
    home = Path(home).absolute(); safe(home)
    config = home / '.codex/config.toml'; guidance = home / '.codex/AGENTS.md'
    safe(config); safe(guidance)
    old_config_bytes = config.read_bytes() if config.exists() else None
    old_config = old_config_bytes.decode() if old_config_bytes is not None else ''
    # Refuse collisions outside the owned block, rather than editing foreign MCP definitions.
    foreign = foreign_config(old_config, home)
    parsed = tomllib.loads(foreign)
    for name in ('quality', 'context7') if context7 else ('quality',):
        if name in parsed.get('mcp_servers', {}):
            raise ValueError('Foreign MCP collision: ' + name)
    files = payload(ast_grep)
    identity = sha(b''.join(k.encode() + b'\0' + v for k, v in files.items()))[:20]
    files['release.json'] = (json.dumps({'files': {k: sha(v) for k, v in files.items()}}, sort_keys=True) + '\n').encode()
    release = home / '.local/share/mycodexconfig/releases' / identity
    safe(release)
    if release.exists():
        for relative, data in files.items():
            p = release / relative; safe(p)
            if not p.is_file() or p.read_bytes() != data: raise ValueError('Modified installed release')
    python = str(Path(sys.executable).resolve())
    desired = {config: managed(foreign, config_block(home, release, python, context7)).encode()}
    tomllib.loads(desired[config].decode())  # validate the full merged configuration before any write
    hook_config = home / '.codex/hooks.json'; safe(hook_config)
    old_hooks = hook_config.read_bytes() if hook_config.exists() else None
    new_hooks, active_hooks, foreign_stop, trust_changed = merge_hooks(old_hooks, home, release, python, workflow_hooks)
    if new_hooks is not None: desired[hook_config] = new_hooks
    result = {'release': str(release)}
    warnings = []
    if foreign_stop:
        warnings.append('Existing Stop hooks can affect workflow guard continuation')
    if trust_changed:
        warnings.append('Workflow guard commands changed. Review hook trust again in Codex before relying on them')
    if active_hooks:
        inline_hooks = parsed.get('hooks', {})
        if isinstance(inline_hooks, dict) and any(isinstance(groups, list) and groups
                                                 for groups in inline_hooks.values()):
            warnings.append('Inline config.toml hooks can interact with workflow guard hooks. Effective behavior is unverified')
        features = parsed.get('features', {})
        if isinstance(features, dict) and features.get('hooks') is False:
            warnings.append('config.toml sets features.hooks = false. Workflow guard execution is unverified')
    if warnings:
        result['warnings'] = warnings
    body = (ROOT / 'guidance.md').read_text().replace('@RUNTIME@', str(release)).replace('@SETTINGS@', str(home / '.config/mycodexconfig/settings.json'))
    desired[guidance] = managed(guidance.read_text() if guidance.exists() else '', body).encode()
    for name in sorted((ROOT / 'skills').iterdir()):
        if not name.is_dir(): continue
        destination = home / '.codex/skills' / name.name
        safe(destination)
        if destination.exists() and (not (destination / 'SKILL.md').is_file() or MARKER not in (destination / 'SKILL.md').read_text()):
            raise ValueError('Foreign skill collision: ' + name.name)
        for p in name.rglob('*'):
            if p.is_file(): desired[destination / p.relative_to(name)] = p.read_text().replace('@RUNTIME@', str(release)).encode()
    settings = home / '.config/mycodexconfig/settings.json'; safe(settings)
    if not settings.exists(): desired[settings] = b'{"projects": []}\n'
    snapshots = {config: old_config_bytes, hook_config: old_hooks}
    changes = {p: v for p, v in desired.items() if not p.exists() or p.read_bytes() != v}
    if not changes:
        if release.exists(): return {'status': 'UNCHANGED', **result}
        deploy_release(release, files)
        return {'status': 'RUNTIME_RESTORED', **result}
    backup = home / '.codex/backups/mycodexconfig' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    safe(backup); backup.mkdir(parents=True, mode=0o700)
    manifest = {'version': 1, 'files': {}, 'release': str(release)}
    for p, data in changes.items():
        relative = str(p.relative_to(home)); old = p.read_bytes() if p.exists() else None
        if p in snapshots and old != snapshots[p]:
            raise ValueError('Concurrent change; refusing install: ' + relative)
        entry = {'before': sha(old) if old is not None else None, 'after': sha(data)}
        if old is not None: atomic(backup / 'files' / relative, old)
        manifest['files'][relative] = entry
    atomic(backup / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    if not release.exists(): deploy_release(release, files)
    applied = []
    try:
        for p, data in changes.items():
            if p in snapshots:
                safe(p)
                if (p.read_bytes() if p.exists() else None) != snapshots[p]:
                    raise ValueError('Concurrent change; refusing install: ' + str(p.relative_to(home)))
            atomic(p, data); applied.append(p)
    except Exception as exc:
        preserved = []
        for p in reversed(applied):
            if not p.is_file() or p.read_bytes() != desired[p]:
                preserved.append(str(p.relative_to(home)))
                continue
            relative = str(p.relative_to(home)); entry = manifest['files'][relative]
            if entry['before'] is None: p.unlink()
            else: atomic(p, (backup / 'files' / relative).read_bytes())
        if preserved:
            raise ValueError('Partial rollback; preserved concurrent edits: ' + ', '.join(preserved) + '; original error: ' + str(exc)) from exc
        raise
    return {'status': 'INSTALLED', **result, 'backup': str(backup), 'changed_files': len(changes)}


def deploy_release(release, files):
    staging = release.parent / ('.stage-' + uuid.uuid4().hex)
    for relative, data in files.items(): atomic(staging / relative, data)
    if 'bin/ast-grep' in files: (staging / 'bin/ast-grep').chmod(0o755)
    os.replace(staging, release)


def rollback(home, backup):
    home = Path(home).absolute(); backup = Path(backup).absolute(); safe(home); safe(backup)
    expected_root = home / '.codex/backups/mycodexconfig'
    if backup.parent != expected_root: raise ValueError('Backup must belong to this Codex home')
    manifest = json.loads((backup / 'manifest.json').read_text())
    for relative, entry in manifest['files'].items():
        p = home / relative; safe(p)
        if Path(relative).is_absolute() or '..' in Path(relative).parts: raise ValueError('Unsafe backup path')
        if not p.is_file() or sha(p.read_bytes()) != entry['after']: raise ValueError('Concurrent change; refusing rollback: ' + relative)
        if entry['before'] is not None:
            old = backup / 'files' / relative; safe(old)
            if sha(old.read_bytes()) != entry['before']: raise ValueError('Backup integrity failure')
    for relative, entry in manifest['files'].items():
        p = home / relative
        if entry['before'] is None: p.unlink()
        else: atomic(p, (backup / 'files' / relative).read_bytes())
    return {'status': 'ROLLED_BACK', 'files': len(manifest['files'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--without-context7', action='store_true')
    parser.add_argument('--rollback', type=Path)
    hooks = parser.add_mutually_exclusive_group()
    hooks.add_argument('--workflow-hooks', action='store_true', help='Enable the MyCodexConfig workflow guard hooks')
    hooks.add_argument('--without-workflow-hooks', dest='workflow_hooks', action='store_false',
                       help='Remove the MyCodexConfig workflow guard hooks')
    parser.set_defaults(workflow_hooks=None)
    parser.add_argument('--ast-grep', type=Path, help='Copy a verified existing ast-grep executable into the independent runtime')
    args = parser.parse_args()
    try:
        result = rollback(args.home, args.rollback) if args.rollback else install(
            args.home, not args.without_context7, args.ast_grep, workflow_hooks=args.workflow_hooks)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__': raise SystemExit(main())
