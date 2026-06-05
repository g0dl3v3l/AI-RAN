# Experiments

This README is intentionally narrow. It covers V0 verification for the current experiment harness, so you can prove the harness wrote the expected artifact set, Docker and CRIU worked on the experiment-owned smoke container, vLLM came up, and the smoke request finished after restore completion.

Pytest skips integration and GPU cases unless you opt in with env vars. From the repo root, run:

```bash
pytest experiments/tests
AI_EDGE_RUN_INTEGRATION=1 pytest experiments/tests
AI_EDGE_RUN_GPU=1 pytest experiments/tests
```

## V0 Verification: Docker + CRIU + vLLM

V0 verification has three layers.

1. `docker_criu_integration.json` proves Docker checkpoint and restore worked for the experiment-owned BusyBox smoke container.
2. `runtime_check.json` plus `smoke_preemption.json` prove the vLLM runtime started and the experiment-owned vLLM container reached the restore step.
3. `smoke_validation.json` plus `smoke_response.jsonl` prove the in-flight request produced a successful response after restore completion.

`experiments/scripts/run_v0_probe.py` always tears down its experiment-owned Docker runtime before exit. Live `/v1/models` and `/v1/chat/completions` checks need to happen while a temporary vLLM session is still running. After the process exits, the JSON and JSONL artifacts are the source of truth.

### 1. Prove the dry-run wrote the full V0 artifact set

Run a dry-run first. This does not prove Docker, CRIU, or vLLM worked. It only proves the harness wrote the complete V0 artifact contract.

```bash
PYTHONPATH=experiments/src python experiments/scripts/run_v0_probe.py \
  --config experiments/configs/v0_env_probe.yaml \
  --output-dir /tmp/ai-edge-v0-verify-dry-run \
  --dry-run

python - <<'PY'
from pathlib import Path

required = {
    'hardware.json',
    'docker.json',
    'criu_check.json',
    'docker_criu_integration.json',
    'cuda_check.json',
    'mps_check.json',
    'runtime_check.json',
    'smoke_request.jsonl',
    'smoke_response.jsonl',
    'smoke_preemption.json',
    'smoke_validation.json',
    'run_metadata.json',
    'config.yaml',
}
run_dir = Path('/tmp/ai-edge-v0-verify-dry-run')
found = {path.name for path in run_dir.iterdir() if path.is_file()}
missing = sorted(required - found)
extra = sorted(found - required)
assert not missing, {'missing': missing}
assert not extra, {'extra': extra}
print('dry-run artifact set ok')
PY
```

### 2. Bring up a temporary live vLLM session and check the endpoints

The committed config is safe by default. It keeps `runtime_options.vllm.external_server.enabled: false`, `runtime_options.vllm.docker_server.enabled: false`, and `model: null`, so it will classify the runtime as skipped. For the reproducible live vLLM path on this host, create a copied config that keeps the external-server path disabled, turns on the Docker runtime, and uses a small public model.

```bash
export V0_MODEL="Qwen/Qwen2-0.5B-Instruct"

python - <<'PY'
from pathlib import Path
import yaml

src = Path('experiments/configs/v0_env_probe.yaml')
dst = Path('/tmp/v0_env_probe.real.yaml')
config = yaml.safe_load(src.read_text(encoding='utf-8'))
config['model'] = config['runtime_options']['vllm']['docker_server']['model'] = __import__('os').environ['V0_MODEL']
config['runtime_options']['vllm']['external_server']['enabled'] = False
config['runtime_options']['vllm']['external_server']['base_url'] = None
config['runtime_options']['vllm']['docker_server']['enabled'] = True
config['output_dir'] = '/tmp/ai-edge-v0-verify-real'
dst.write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
print(dst)
PY
```

The `vllm/vllm-openai` image entrypoint already runs `vllm serve`, so `docker_server.extra_args` should contain only model/server flags and must not include an extra `serve` token.

In shell A, leave this process running while you do the curl checks in shell B.

```bash
PYTHONPATH=experiments/src python - <<'PY'
from pathlib import Path
import yaml
from ai_runtime_experiments.runtime_adapters import VLLMRuntimeAdapter

config = yaml.safe_load(Path('/tmp/v0_env_probe.real.yaml').read_text(encoding='utf-8'))
adapter = VLLMRuntimeAdapter(
    config=config['runtime_options']['vllm'],
    timeout_s=float(config['probe_options']['runtime']['timeout_s']),
)
session = adapter.start(run_id='v0-live-check')
print({'status': session.runtime_check['status'], 'base_url': session.base_url, 'container_name': session.container_name})
if session.runtime_check['status'] != 'ok' or not session.base_url:
    raise SystemExit('vLLM did not start, inspect runtime_check details before continuing')
input('Run the curl checks in another shell, then press Enter here to stop the container...')
cleanup = adapter.stop(session)
print(cleanup)
PY
```

In shell B, verify both the model listing and a real chat completion against the live server.

```bash
curl -sS http://localhost:8000/v1/models | python -m json.tool

curl -sS http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer EMPTY' \
  -d "$(python - <<'PY'
import json
from pathlib import Path
import yaml

config = yaml.safe_load(Path('/tmp/v0_env_probe.real.yaml').read_text(encoding='utf-8'))
payload = {
    'model': config['model'],
    'messages': [{'role': 'user', 'content': config['workload']['prompt']}],
    'temperature': config['workload']['temperature'],
    'max_tokens': config['workload']['max_tokens'],
}
print(json.dumps(payload))
PY
)" | python -m json.tool
```

If `/v1/models` returns a model list and `/v1/chat/completions` returns a normal OpenAI-compatible response, the vLLM runtime is reachable before the full V0 probe.

### 3. Run the full V0 probe and inspect the post-run artifacts

Run the real probe with the runtime-enabled config.

```bash
PYTHONPATH=experiments/src python experiments/scripts/run_v0_probe.py \
  --config /tmp/v0_env_probe.real.yaml \
  --output-dir /tmp/ai-edge-v0-verify-real
```

Print the core verification records.

```bash
python - <<'PY'
import json
from pathlib import Path

run_dir = Path('/tmp/ai-edge-v0-verify-real')
for name in [
    'docker_criu_integration.json',
    'runtime_check.json',
    'smoke_preemption.json',
    'smoke_validation.json',
]:
    data = json.loads((run_dir / name).read_text(encoding='utf-8'))
    print(name, {
        'status': data.get('status'),
        'classification': data.get('classification'),
        'outcome': (data.get('details') or {}).get('outcome'),
        'reason': (data.get('details') or {}).get('reason'),
    })
PY
```

Check the final smoke response record as well.

```bash
python - <<'PY'
import json
from pathlib import Path

run_dir = Path('/tmp/ai-edge-v0-verify-real')
validation = json.loads((run_dir / 'smoke_validation.json').read_text(encoding='utf-8'))
responses = [
    json.loads(line)
    for line in (run_dir / 'smoke_response.jsonl').read_text(encoding='utf-8').splitlines()
    if line
]
last = responses[-1]
print({
    'validation_classification': validation['classification'],
    'request_id': validation.get('request_id'),
    'response_status': last.get('status'),
    'assistant_text': (last.get('extracted') or {}).get('assistant_text'),
})
PY
```

### 4. Interpret the three verification layers

| Layer | Artifact or command | Pass condition | Meaning |
| --- | --- | --- | --- |
| Dry-run artifact contract | `/tmp/ai-edge-v0-verify-dry-run` | Required file set matches exactly | The harness can emit the full V0 artifact set without host side effects. |
| Docker + CRIU smoke path | `docker_criu_integration.json` | `status == "ok"` | Docker checkpoint and restore worked for the experiment-owned BusyBox smoke container. This is the Docker + CRIU proof point. |
| vLLM startup | live `curl -sS http://localhost:8000/v1/models` and `runtime_check.json` | curl returns JSON and `runtime_check.json.status == "ok"` | The vLLM runtime came up and answered the OpenAI-compatible API before the full probe. |
| vLLM restore step | `smoke_preemption.json` | `status == "ok"` and `details.outcome == "restored"` | The experiment-owned vLLM container reached checkpoint, stop, restore, and post-restore `docker inspect` successfully. |
| In-flight request completed | `smoke_validation.json` and `smoke_response.jsonl` | `classification` is `smoke_completed_after_restore`, and the last response record has `status == "ok"` | The request produced a successful response after restore completion. Current V0 does not implement or verify a replay execution path. |

Use `smoke_validation.json` as the final decision record.

| `smoke_validation.json.classification` | Meaning | Verdict |
| --- | --- | --- |
| `smoke_completed_after_restore` | The strongest V0 result. A successful smoke response was observed after restore completed. | pass |
| `smoke_replayed` | Reserved for a future explicit replay flow. Current V0 does not execute or verify replay, so this classification should not be treated as a V0 success signal. | not expected in current V0 |
| `smoke_failed_restore` | The checkpoint or restore command failed. Check `smoke_preemption.json.details.commands`. | fail |
| `smoke_runtime_failed` | Restore commands returned, but the runtime container was not running after restore. | fail |
| `smoke_hung` | A checkpoint, restore, or follow-up probe timed out. | fail |
| `smoke_not_supported` | The host or Docker daemon does not support the required checkpoint path. | expected unsupported |
| `smoke_not_attempted` | The runtime never became preemptible, or no successful post-restore response was proven, or you only ran the dry-run path. | expected skipped |

`docker_criu_integration.json.status == "ok"` by itself is not enough to claim vLLM checkpoint success. That file only proves the Docker + CRIU smoke path worked on the experiment-owned CPU container. To claim the full V0 path worked, you need all of these together:

* `docker_criu_integration.json.status == "ok"`
* `runtime_check.json.status == "ok"`
* `smoke_preemption.json.status == "ok"`
* `smoke_validation.json.classification == "smoke_completed_after_restore"`

For later automation, keep `experiments/examples/v0_env_probe/verification_checklist.example.json` next to the run artifacts and evaluate the checks in order. The JSON file uses the same layer names, artifact names, and result meanings as this section.
