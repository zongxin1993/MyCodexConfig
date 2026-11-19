# Rust review lenses

Use the approved contract and affected callers to select the lenses; don't demand every tool for every task.

- API/error semantics: invalid/empty/boundary input, numeric overflow/casts/rounding, stable ordering, state changes on failure, Result/Option categories and causal context. Check observable behavior independently of implementation-shaped tests; avoid unwrap/expect in reachable fallible paths unless the invariant is justified.
- Ownership/structure: responsibility boundaries, public surface and dependency direction; unnecessary clones/allocations or Arc/Mutex used to conceal an ownership problem. Read declarations and callers before recommending lifetime/type changes.
- Shared state/async: lock scope across await, cancellation/partial writes, Send/Sync requirements, retry/idempotency and recovery. Compiler success does not establish race freedom or durable recovery. Use actual concurrency/failure tests for relevant requirements.
- Unsafe/FFI: identify each invariant, pointer lifetime/alignment/aliasing, bounds and panic/unwind boundary. Missing unsafe/platform evidence stays open. Consider Miri/sanitizers only on supported, explicitly selected lanes; no automatic toolchain switch.
- Tests/evidence: inspect tests themselves and independently chosen negative/boundary cases. Distinguish unit/integration/doc tests, host/target, feature sets and profiles. Verify original command, cwd, exit status and current source hashes; stale green logs do not approve changed bytes. No blanket lint suppression or relaxed assertions to close findings.

Return codex-quality-review's severity/impact/urgency/fix-value fields and stable IDs. Failed approved behavior blocks acceptance even if all Cargo commands are green. A clean verdict names omitted lanes (MSRV, other targets/features, unsafe/concurrency, external services) without claiming they passed.
