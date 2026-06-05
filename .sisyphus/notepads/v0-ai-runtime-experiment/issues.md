# Issues


## 2026-06-04 23:00:14Z

- Pyright LSP reported `ai_runtime_experiments` as an unresolved import in the smoke test (workspace analysis doesn't inherit `PYTHONPATH=experiments/src`). Mitigated with an inline `# pyright: ignore[reportMissingImports]` on the import line.

## 2026-06-05T03:07:03Z

- Final QA found that the README’s repo-root test command `pytest experiments/tests` is not runnable as documented on a clean checkout: pytest collection fails with `ModuleNotFoundError: No module named 'ai_runtime_experiments'` across the unit suite. The same suite passes with `PYTHONPATH=experiments/src pytest experiments/tests`, so this is a concrete operator-workflow/documentation failure rather than an underlying harness failure.

## 2026-06-05T03:15:39Z

- Final reviewer gap 1 was real: `.gitignore` only covered `experiments/results/**` and traces, so generated `experiments/checkpoints/**`, `experiments/logs/**`, and `experiments/models/**` artifacts were still unguarded.
- Final reviewer gap 2 was real: live `LLMSmokeClient` JSONL records lacked the shared V0 artifact fields (`status`, `component`, `details`) that dry-run placeholders and probe artifacts already emitted.
