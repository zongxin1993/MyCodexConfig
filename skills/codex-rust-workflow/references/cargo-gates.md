# Choosing Cargo verification

1. Read the repository's command wrapper and CI first. Inspect toolchain/manifest without executing untrusted build scripts when deciding scope. `cargo metadata --no-deps --format-version 1` describes workspace members and features; it is not a build or test result. Dependency resolution can still need registry access. Record the selected package(s), features, target and toolchain with each check.
2. Reuse the pinned toolchain. Record `rustc -Vv`, `cargo -V`, `cargo clippy -V`. MSRV is a separate lane from current stable. Do not infer cross-platform or MSRV success from a host-only build.
3. For a small workspace with a committed lockfile and cached/no dependencies, suitable commands are:

```sh
cargo fmt --all -- --check
cargo build --workspace --all-targets --locked --offline
cargo clippy --workspace --all-targets --locked --offline -- -D warnings
cargo test --workspace --locked --offline
cargo test --workspace --doc --locked --offline
```

`cargo check` can shorten an edit cycle; it does not replace a required linked build. `--all-targets` also checks test/example/bench targets, but default `cargo test` and explicit doctests must still be selected as required. `--locked` fails if resolution would change the lockfile; do not use it before a project-authorized initial lockfile creation. `--offline` needs cached dependencies; a cache failure is not a source defect. Preserve original output and exit codes even when RTK condenses the display.

4. Default, no-default and named feature sets may differ. `--all-features` is not universally valid (mutually exclusive backends/platforms) and cannot prove all combinations. Choose combinations from affected code and project policy. Release/debug overflow and cfg behavior can differ; run the affected profiles when semantics warrant it.
5. For a real compiler/lint failure save the diagnostic first, repair its responsible boundary, rerun that command and the relevant behavior tests. Keep failing regression evidence before the fix. An unrelated pre-existing failure remains visible and blocks a required lane unless the user explicitly defers it.

Sources: Cargo build/test/check reference at https://doc.rust-lang.org/cargo/commands/; Clippy usage at https://doc.rust-lang.org/clippy/usage.html; rustfmt at https://github.com/rust-lang/rustfmt.
