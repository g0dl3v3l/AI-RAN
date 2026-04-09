from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from inference_profile import cli, opt_assets


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


@pytest.mark.remote_mock
def test_inspect_model_cli_uses_synthetic_fallback_for_monolithic_only_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_json(
        tmp_path / "config.json",
        {
            "hidden_size": 768,
            "num_hidden_layers": 12,
            "num_attention_heads": 12,
            "ffn_dim": 3072,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 768,
            "do_layer_norm_before": True,
        },
    )
    config_calls: list[str] = []
    index_calls: list[str] = []

    def fake_download_repo_file(
        repo_id: str,
        filename: str,
        cache_root: Path | None = None,
    ) -> Path:
        del repo_id, cache_root
        config_calls.append(filename)
        assert filename == opt_assets.CONFIG_FILENAME
        return config_path

    def fake_try_download_repo_file(
        repo_id: str,
        filename: str,
        cache_root: Path | None = None,
    ) -> Path | None:
        del repo_id, cache_root
        index_calls.append(filename)
        return None

    monkeypatch.setattr(opt_assets, "_download_repo_file", fake_download_repo_file)
    monkeypatch.setattr(
        opt_assets,
        "_try_download_repo_file",
        fake_try_download_repo_file,
    )
    monkeypatch.setattr(
        opt_assets,
        "_list_repo_files",
        lambda model_id: (opt_assets.CONFIG_FILENAME, "pytorch_model.bin"),
    )
    monkeypatch.setattr(
        opt_assets,
        "snapshot_download",
        lambda *args, **kwargs: pytest.fail(
            "snapshot_download should not be used for monolithic-only repos"
        ),
    )
    monkeypatch.setattr(
        opt_assets,
        "_detect_total_gpu_memory_bytes",
        lambda: 32_000_000_000,
    )

    output_root = tmp_path / "inspect-out"
    exit_code = cli.main(
        [
            "inspect-model",
            "--model",
            "facebook/opt-125m",
            "--output-root",
            str(output_root),
        ]
    )

    assert exit_code == 0
    assert config_calls == ["config.json"]
    assert index_calls == [
        "model.safetensors.index.json",
        "pytorch_model.bin.index.json",
    ]

    model_constants = json.loads(
        (output_root / "raw" / opt_assets.MODEL_CONSTANTS_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    asset_manifest = json.loads(
        (output_root / "raw" / opt_assets.ASSET_MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )

    assert model_constants == {
        "num_hidden_layers": 12,
        "hidden_size": 768,
        "num_attention_heads": 12,
        "ffn_dim": 3072,
        "layer_index": 5,
        "layer_weight_bytes": 14_175_744,
        "total_weight_bytes_fp16": 250_478_592,
        "vram_ceiling_bytes": 19_200_000_000,
    }
    assert asset_manifest["asset_source"] == "synthetic_fallback"
    assert asset_manifest["asset_source_reason"] == "monolithic_only"
    assert asset_manifest["resolved_shard_filenames"] == []
    assert asset_manifest["resolved_shard_paths"] == []
    assert asset_manifest["layer_prefix"] is None
    assert asset_manifest["synthetic_layer"]["seed"] == 47


@pytest.mark.remote_mock
def test_inspect_model_cli_downloads_only_selected_layer_shards_from_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_json(
        tmp_path / "config.json",
        {
            "hidden_size": 4096,
            "num_hidden_layers": 32,
            "num_attention_heads": 32,
            "ffn_dim": 16384,
            "max_position_embeddings": 2048,
            "vocab_size": 50272,
            "word_embed_proj_dim": 4096,
            "do_layer_norm_before": True,
            "_remove_final_layer_norm": False,
        },
    )
    index_path = _write_json(
        tmp_path / "pytorch_model.bin.index.json",
        {
            "weight_map": {
                "decoder.layers.15.fc1.weight": "pytorch_model-00001-of-00002.bin",
                "decoder.layers.15.fc1.bias": "pytorch_model-00001-of-00002.bin",
                "decoder.layers.15.fc2.weight": "pytorch_model-00002-of-00002.bin",
                "decoder.layers.15.fc2.bias": "pytorch_model-00002-of-00002.bin",
                "decoder.layers.3.fc1.weight": "pytorch_model-00001-of-00002.bin",
            }
        },
    )
    config_calls: list[str] = []
    index_calls: list[str] = []
    snapshot_calls: list[list[str]] = []

    def fake_download_repo_file(
        repo_id: str,
        filename: str,
        cache_root: Path | None = None,
    ) -> Path:
        del repo_id, cache_root
        config_calls.append(filename)
        assert filename == opt_assets.CONFIG_FILENAME
        return config_path

    def fake_try_download_repo_file(
        repo_id: str,
        filename: str,
        cache_root: Path | None = None,
    ) -> Path | None:
        del repo_id, cache_root
        index_calls.append(filename)
        if filename == "pytorch_model.bin.index.json":
            return index_path
        return None

    def fake_snapshot_download(
        repo_id: str,
        allow_patterns: list[str],
        cache_dir: Path | None = None,
    ) -> str:
        del repo_id, cache_dir
        snapshot_calls.append(list(allow_patterns))
        snapshot_root = tmp_path / "snapshot"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        for filename in allow_patterns:
            path = snapshot_root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"layer-shard")
        return str(snapshot_root)

    monkeypatch.setattr(opt_assets, "_download_repo_file", fake_download_repo_file)
    monkeypatch.setattr(
        opt_assets,
        "_try_download_repo_file",
        fake_try_download_repo_file,
    )
    monkeypatch.setattr(
        opt_assets,
        "_list_repo_files",
        lambda model_id: pytest.fail(
            "list_repo_files should not be used when a usable shard index exists"
        ),
    )
    monkeypatch.setattr(opt_assets, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(
        opt_assets,
        "_detect_total_gpu_memory_bytes",
        lambda: 32_000_000_000,
    )

    output_root = tmp_path / "inspect-out"
    exit_code = cli.main(
        [
            "inspect-model",
            "--model",
            "facebook/opt-6.7b",
            "--output-root",
            str(output_root),
        ]
    )

    assert exit_code == 0
    assert config_calls == ["config.json"]
    assert index_calls == [
        "model.safetensors.index.json",
        "pytorch_model.bin.index.json",
    ]
    assert snapshot_calls == [
        [
            "pytorch_model-00001-of-00002.bin",
            "pytorch_model-00002-of-00002.bin",
        ]
    ]

    model_constants = json.loads(
        (output_root / "raw" / opt_assets.MODEL_CONSTANTS_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    asset_manifest = json.loads(
        (output_root / "raw" / opt_assets.ASSET_MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )

    assert model_constants == {
        "num_hidden_layers": 32,
        "hidden_size": 4096,
        "num_attention_heads": 32,
        "ffn_dim": 16384,
        "layer_index": 15,
        "layer_weight_bytes": 402_759_680,
        "total_weight_bytes_fp16": 13_316_947_968,
        "vram_ceiling_bytes": 19_200_000_000,
    }
    assert asset_manifest["asset_source"] == "layer_shard"
    assert asset_manifest["asset_source_reason"] == "indexed_layer_shard"
    assert asset_manifest["index_filename"] == "pytorch_model.bin.index.json"
    assert asset_manifest["layer_prefix"] == "decoder.layers.15."
    assert asset_manifest["resolved_shard_filenames"] == [
        "pytorch_model-00001-of-00002.bin",
        "pytorch_model-00002-of-00002.bin",
    ]
    assert [Path(path).name for path in asset_manifest["resolved_shard_paths"]] == [
        "pytorch_model-00001-of-00002.bin",
        "pytorch_model-00002-of-00002.bin",
    ]
    assert asset_manifest["synthetic_layer"] is None


def test_inspect_model_cli_rejects_unsupported_model_without_traceback(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    output_root = tmp_path / "inspect-out"

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "inference_profile.cli",
            "inspect-model",
            "--model",
            "opt-999m",
            "--output-root",
            str(output_root),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert result.stderr == "Error: Unsupported OPT model 'opt-999m'\n"
    assert "Traceback" not in result.stderr
