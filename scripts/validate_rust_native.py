#!/usr/bin/env python3
"""Private real low-effort Codex Rust fixture; never submit raw session evidence."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from validate_native import call, git, staging_home, verdict, assert_identities
from check_rust_fixture import check, source_hashes


def inject(text):
    pos = text.index('{', text.index('pub fn reserve')) + 1
    return text[:pos] + '\n    if available == 65_536 && requested == available {\n        return Err(ReserveError::Insufficient);\n    }' + text[pos:]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home', required=True, type=Path); p.add_argument('--fixture', required=True, type=Path)
    args = p.parse_args(); args.home = staging_home(args.home); base = args.fixture.resolve(); base.mkdir(mode=0o700)
    primary = base / 'primary'
    shutil.copytree(Path(__file__).resolve().parents[1] / 'examples/rust-reservation', primary, ignore=shutil.ignore_patterns('target', '.git', '.private'))
    evidence = base / 'evidence'; evidence.mkdir(mode=0o700)
    (primary / 'AGENTS.md').write_text('Private Rust validation fixture. Native verification only. Primary checkout is read-only; edit only src/lib.rs and tests/*.rs in the linked worktree. No commits, network, dependency/toolchain changes or new governance files. Use Cargo fmt/build/Clippy (-D warnings)/unit/integration/doc/release tests with --locked --offline where applicable. The environment already provides the test-private toolchain. No nested agents.\n')
    (primary / '.gitignore').write_text('target/\n')
    git(primary, 'init'); git(primary, 'config', 'user.name', 'Fixture'); git(primary, 'config', 'user.email', 'fixture@example.invalid')
    git(primary, 'add', '.'); git(primary, 'commit', '-m', 'Rust fixture baseline')
    baseline = git(primary, 'rev-parse', 'HEAD'); original = source_hashes(primary)
    wt = base / 'worktree'; git(primary, 'worktree', 'add', '-b', 'fixture/rust', str(wt))
    src = wt / 'src/lib.rs'; correct = src.read_text()
    # Negative controls use only disposable fixture bytes, then restore them.
    probes = []
    for name, text, command in [
        ('compiler', correct + '\npub fn broken() -> u32 { "wrong type" }\n', ['cargo','build','--locked','--offline']),
        ('clippy', correct + '\npub fn lint_probe() -> bool { let value = true; value }\n', ['cargo','clippy','--locked','--offline','--','-D','warnings']),
    ]:
        src.write_text(text)
        r = subprocess.run(command, cwd=wt, capture_output=True, text=True, timeout=180)
        (evidence / (name + '-negative.log')).write_text(r.stdout + r.stderr)
        expected = 'E0308' if name == 'compiler' else 'clippy::let_and_return'
        if r.returncode == 0 or expected not in r.stderr:
            raise RuntimeError(name + ' negative control lacked expected diagnostic')
        probes.append({'lane': name, 'command': command, 'exit_code': r.returncode})
    src.write_text(correct)
    # The worker starts from an implementation stub with the public API preserved.
    start = correct.index('    if requested == 0'); end = correct.index('\n}\n', start)
    src.write_text(correct[:start] + '    todo!("implement approved contract")' + correct[end:])
    prefix = ('This is a private disposable fixture. Scripted approvals apply only to this fixture. '
              'Use installed codex-workflow, codex-rust-workflow and appropriate diagnostic/review skills, quality MCP and native tools. '
              'Respect AGENTS.md; no external or OpenCode directories. Chinese stage/status responses. ')
    requirements = ('REQ-1: reserve(available:u32, requested:u32) accepts every positive requested <= available and returns available-requested, including exact depletion and the full u32 domain. '
                    'REQ-2: zero request returns ZeroRequest (even at zero capacity), excess returns Insufficient; caller state is unchanged. No arbitrary limits or panic/wrapping. ')
    clarified_source = source_hashes(wt)
    first = call(args.home, wt, evidence, '01-clarification', prefix + '需求：实现容量预留。提出一个最关键的澄清问题；只读。', readonly=True)
    if source_hashes(wt) != clarified_source: raise RuntimeError('Read-only clarification changed source')
    worker = first['session']
    planned_source = source_hashes(wt)
    plan = call(args.home, wt, evidence, '02-plan', prefix + requirements + '测试操作者已确认以上需求。只读列出验收案例、验证矩阵和计划，等待批准。', session=worker, readonly=True)
    if source_hashes(wt) != planned_source: raise RuntimeError('Read-only planning changed source')
    plan_review = call(args.home, wt, evidence, '02b-independent-plan-review', prefix + requirements + '独立只读审查此计划的边界、验收、验证矩阵；不要编辑。最后一行 VERDICT: PASS 或 VERDICT: BLOCKED。\n' + '\n'.join(plan['messages']), readonly=True)
    if plan_review['session'] == worker: raise RuntimeError('Plan review is not independent')
    verdict(plan_review, 'PASS')
    call(args.home, wt, evidence, '03-implementation', prefix + requirements + '测试操作者批准该 fixture 计划。实现、增加行为测试，执行 Cargo 门禁后等待独立审计。实际读取相关 Rust 技能和参考资料，不提交。', session=worker)
    initial = check(wt, evidence / 'initial-checks')
    if initial['status'] != 'PASS': raise RuntimeError('Initial Cargo gates failed')
    # A source-level seeded defect; the reviewer receives the contract, never its location/trigger.
    src.write_text(inject(src.read_text()))
    subprocess.run(['cargo','fmt','--all'], cwd=wt, check=True)
    mutation = check(wt, evidence / 'mutation-checks')
    if mutation['status'] != 'PASS': raise RuntimeError('Existing tests already catch seed; choose a separate documented seed')
    review_source = source_hashes(wt)
    review = call(args.home, wt, evidence, '04-independent-review', prefix + requirements + '独立只读审计当前源码、调用和测试，实际加载 codex-quality-review 及 Rust 审计参考资料。核对需求和边界，报告稳定问题ID、位置、严重性、影响范围、紧迫性、成本及修复价值，不编辑。最后一行必须是 VERDICT: BLOCKED 或 VERDICT: PASS。', readonly=True)
    if review['session'] in (worker, plan_review['session']): raise RuntimeError('Reviewer is not independent')
    if source_hashes(wt) != review_source: raise RuntimeError('Reviewer modified source')
    verdict(review, 'BLOCKED')
    repair = call(args.home, wt, evidence, '05-same-worker-repair', prefix + requirements + '独立审计结果如下，请核对当前源码，先用回归测试复现问题，修复、执行全部门禁，保留问题ID和失败/通过证据，不提交：\n' + '\n'.join(review['messages']), session=worker)
    assert_identities(worker, review['session'], repair['session'])
    repaired = check(wt, evidence / 'repair-checks')
    if repaired['status'] != 'PASS': raise RuntimeError('Repair Cargo gates failed')
    # Reintroduce exactly the seed against the repaired tests: an observed test failure
    # proves the repair added effective regression coverage, not merely green prose.
    repaired_text = src.read_text()
    try:
        src.write_text(inject(repaired_text))
        r = subprocess.run(['cargo', 'test', '--workspace', '--locked', '--offline'], cwd=wt, capture_output=True, text=True, timeout=180)
        (evidence / 'regression-seed.log').write_text(r.stdout + r.stderr)
        if r.returncode == 0 or 'test result: FAILED' not in r.stdout:
            raise RuntimeError('Repaired tests did not reject the semantic seed')
    finally:
        src.write_text(repaired_text)
    frozen = source_hashes(wt)
    rereview = call(args.home, wt, evidence, '06-independent-rereview', prefix + requirements + f'独立只读复审当前修复源码、测试及原问题。隔离验证进程已完成原生门禁，读取 {evidence / "repair-checks/checks.json"} 和同目录原始日志、{evidence / "regression-seed.log"}，核对源码摘要与实际当前文件。Cargo 编译/测试需要写 target，在只读审计沙箱中不要重跑这类命令；如无法核实已有证据应 BLOCKED。逐项关闭问题，明确区分外部执行证据与审查者自己运行的检查，说明未验证范围。最后一行必须是 VERDICT: PASS 或 VERDICT: BLOCKED。', session=review['session'], readonly=True)
    verdict(rereview, 'PASS')
    if source_hashes(wt) != frozen: raise RuntimeError('Source changed during review')
    if git(primary, 'status', '--porcelain') or git(primary, 'rev-parse', 'HEAD') != baseline or source_hashes(primary) != original:
        raise RuntimeError('Primary changed')
    result = {'status':'PASS', 'fixture_only':True, 'reasoning_effort':'low', 'worker':worker,
              'reviewer':review['session'], 'independent_reviewer':worker != review['session'],
              'same_worker_repaired':worker == repair['session'], 'primary_unchanged':True,
              'negative_controls':probes, 'mutation_existing_gates':mutation['status'],
              'regression_seed_rejected':True, 'checks':repaired, 'private_evidence':str(evidence)}
    (evidence / 'summary.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
