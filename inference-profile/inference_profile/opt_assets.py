from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.errors import (
    EntryNotFoundError,
    LocalEntryNotFoundError,
    RemoteEntryNotFoundError,
)

from inference_profile.constants import OPT_MODEL_IDS

CONFIG_FILENAME = "config.json"
INDEX_FILENAMES = (
    "model.safetensors.index.json",
    "pytorch_model.bin.index.json",
)
MONOLITHIC_FILENAMES = (
    "model.safetensors",
    "pytorch_model.bin",
)
MODEL_CONSTANTS_FILENAME = "model_constants.json"
ASSET_MANIFEST_FILENAME = "asset_manifest.json"

ASSET_SOURCE_LAYER_SHARD = "layer_shard"
ASSET_SOURCE_SYNTHETIC_FALLBACK = "synthetic_fallback"

FP16_BYTES_PER_PARAMETER = 2
KV_BYTES_PER_HIDDEN_VALUE = 4
OPT_POSITION_EMBEDDING_OFFSET = 2
SYNTHETIC_LAYER_SEED_BASE = 42
VRAM_CEILING_FRACTION_NUMERATOR = 60
VRAM_CEILING_FRACTION_DENOMINATOR = 100

_MISSING_ENTRY_ERRORS = (
    EntryNotFoundError,
    LocalEntryNotFoundError,
    RemoteEntryNotFoundError,
)
_REQUIRED_CONFIG_FIELDS = (
    "hidden_size",
    "num_hidden_layers",
    "num_attention_heads",
    "ffn_dim",
    "max_position_embeddings",
    "vocab_size",
)


@dataclass(frozen=True)
class OptConfig:
    model_id: str
    hidden_size: int
    num_hidden_layers: int
    num_attention_heads: int
    ffn_dim: int
    max_position_embeddings: int
    vocab_size: int
    word_embed_proj_dim: int
    head_dim: int
    final_layer_norm_enabled: bool

    @property
    def layer_parameter_count(self) -> int:
        hidden_size = self.hidden_size
        ffn_dim = self.ffn_dim
        return (
            (4 * hidden_size * hidden_size)
            + (2 * hidden_size * ffn_dim)
            + ffn_dim
            + (9 * hidden_size)
        )

    @property
    def layer_weight_bytes(self) -> int:
        return self.layer_parameter_count * FP16_BYTES_PER_PARAMETER

    @property
    def kv_bytes_per_token_all_layers(self) -> int:
        return KV_BYTES_PER_HIDDEN_VALUE * self.hidden_size * self.num_hidden_layers

    @property
    def total_parameter_count(self) -> int:
        hidden_size = self.hidden_size
        word_embed_proj_dim = self.word_embed_proj_dim
        embedding_parameters = self.vocab_size * word_embed_proj_dim
        position_embedding_parameters = (
            self.max_position_embeddings + OPT_POSITION_EMBEDDING_OFFSET
        ) * hidden_size
        project_in_parameters = 0
        project_out_parameters = 0
        if word_embed_proj_dim != hidden_size:
            project_in_parameters = word_embed_proj_dim * hidden_size
            project_out_parameters = hidden_size * word_embed_proj_dim
        final_norm_parameters = 2 * hidden_size if self.final_layer_norm_enabled else 0
        return (
            embedding_parameters
            + position_embedding_parameters
            + project_in_parameters
            + project_out_parameters
            + (self.num_hidden_layers * self.layer_parameter_count)
            + final_norm_parameters
        )

    @property
    def total_weight_bytes_fp16(self) -> int:
        return self.total_parameter_count * FP16_BYTES_PER_PARAMETER

    def model_constants(
        self, layer_index: int, vram_ceiling_bytes: int
    ) -> dict[str, int]:
        return {
            "num_hidden_layers": self.num_hidden_layers,
            "hidden_size": self.hidden_size,
            "num_attention_heads": self.num_attention_heads,
            "ffn_dim": self.ffn_dim,
            "layer_index": layer_index,
            "layer_weight_bytes": self.layer_weight_bytes,
            "total_weight_bytes_fp16": self.total_weight_bytes_fp16,
            "vram_ceiling_bytes": int(vram_ceiling_bytes),
        }


@dataclass(frozen=True)
class InspectionResult:
    model_id: str
    output_root: Path
    model_constants_path: Path
    asset_manifest_path: Path
    model_constants: dict[str, int]
    asset_manifest: dict[str, Any]
    asset_source: str
    resolved_shard_filenames: tuple[str, ...]


def normalize_model_id(model_id: str) -> str:
    normalized = str(model_id).strip()
    if not normalized:
        raise ValueError("model_id must not be empty")
    if not normalized.startswith("facebook/"):
        normalized = f"facebook/{normalized}"
    if normalized not in OPT_MODEL_IDS:
        raise KeyError(f"Unsupported OPT model '{model_id}'")
    return normalized


def select_middle_layer_index(num_hidden_layers: int) -> int:
    total_layers = int(num_hidden_layers)
    if total_layers <= 0:
        raise ValueError("num_hidden_layers must be > 0")
    return (total_layers - 1) // 2


def candidate_layer_prefixes(layer_index: int) -> tuple[str, str]:
    suffix = f"decoder.layers.{int(layer_index)}."
    return (f"model.{suffix}", suffix)


def derive_opt_config(model_id: str, config_payload: Mapping[str, Any]) -> OptConfig:
    repo_id = normalize_model_id(model_id)
    missing_fields = [
        field for field in _REQUIRED_CONFIG_FIELDS if field not in config_payload
    ]
    if missing_fields:
        raise KeyError(
            "OPT config is missing required field(s): "
            + ", ".join(sorted(missing_fields))
        )

    hidden_size = int(config_payload["hidden_size"])
    num_hidden_layers = int(config_payload["num_hidden_layers"])
    num_attention_heads = int(config_payload["num_attention_heads"])
    ffn_dim = int(config_payload["ffn_dim"])
    max_position_embeddings = int(config_payload["max_position_embeddings"])
    vocab_size = int(config_payload["vocab_size"])
    word_embed_proj_dim = int(config_payload.get("word_embed_proj_dim", hidden_size))
    do_layer_norm_before = bool(config_payload.get("do_layer_norm_before", True))
    remove_final_layer_norm = bool(
        config_payload.get("_remove_final_layer_norm", False)
    )

    if hidden_size <= 0:
        raise ValueError("hidden_size must be > 0")
    if num_hidden_layers <= 0:
        raise ValueError("num_hidden_layers must be > 0")
    if num_attention_heads <= 0:
        raise ValueError("num_attention_heads must be > 0")
    if hidden_size % num_attention_heads != 0:
        raise ValueError(
            f"hidden_size {hidden_size} must be divisible by num_attention_heads {num_attention_heads}"
        )
    if ffn_dim <= 0:
        raise ValueError("ffn_dim must be > 0")
    if max_position_embeddings <= 0:
        raise ValueError("max_position_embeddings must be > 0")
    if vocab_size <= 0:
        raise ValueError("vocab_size must be > 0")
    if word_embed_proj_dim <= 0:
        raise ValueError("word_embed_proj_dim must be > 0")

    return OptConfig(
        model_id=repo_id,
        hidden_size=hidden_size,
        num_hidden_layers=num_hidden_layers,
        num_attention_heads=num_attention_heads,
        ffn_dim=ffn_dim,
        max_position_embeddings=max_position_embeddings,
        vocab_size=vocab_size,
        word_embed_proj_dim=word_embed_proj_dim,
        head_dim=hidden_size // num_attention_heads,
        final_layer_norm_enabled=do_layer_norm_before and not remove_final_layer_norm,
    )


def estimate_decoder_layer_weight_bytes_fp16(config: OptConfig) -> int:
    return config.layer_weight_bytes


def estimate_total_weight_bytes_fp16(config: OptConfig) -> int:
    return config.total_weight_bytes_fp16


def estimate_vram_ceiling_bytes(total_gpu_memory_bytes: int | None) -> int:
    if total_gpu_memory_bytes is None:
        return 0
    resolved_total_bytes = int(total_gpu_memory_bytes)
    if resolved_total_bytes <= 0:
        return 0
    return (
        resolved_total_bytes * VRAM_CEILING_FRACTION_NUMERATOR
    ) // VRAM_CEILING_FRACTION_DENOMINATOR


def load_checkpoint_index(
    model_id: str,
    cache_root: str | Path | None = None,
) -> tuple[str, dict[str, Any]] | None:
    repo_id = normalize_model_id(model_id)
    for filename in INDEX_FILENAMES:
        index_path = _try_download_repo_file(repo_id, filename, cache_root)
        if index_path is None:
            continue
        payload = _read_json_object(index_path)
        weight_map = payload.get("weight_map")
        if isinstance(weight_map, Mapping):
            return filename, payload
    return None


def resolve_indexed_layer_shards(
    index_payload: Mapping[str, Any],
    layer_index: int,
) -> tuple[str | None, tuple[str, ...]]:
    weight_map = index_payload.get("weight_map", {})
    if not isinstance(weight_map, Mapping):
        return None, ()
    for prefix in candidate_layer_prefixes(layer_index):
        shard_filenames = sorted(
            {
                str(filename)
                for tensor_name, filename in weight_map.items()
                if str(tensor_name).startswith(prefix)
            }
        )
        if shard_filenames:
            return prefix, tuple(shard_filenames)
    return None, ()


def build_synthetic_layer_metadata(
    config: OptConfig,
    layer_index: int,
    *,
    reason: str,
) -> dict[str, Any]:
    synthetic_seed = SYNTHETIC_LAYER_SEED_BASE + int(layer_index)
    parameters = []
    for index, (name, shape) in enumerate(_synthetic_layer_parameter_shapes(config)):
        numel = _shape_numel(shape)
        parameters.append(
            {
                "name": name,
                "shape": list(shape),
                "numel": numel,
                "bytes_fp16": numel * FP16_BYTES_PER_PARAMETER,
                "seed": synthetic_seed + index,
            }
        )
    return {
        "dtype": "float16",
        "reason": reason,
        "seed": synthetic_seed,
        "parameters": parameters,
    }


def inspect_model(
    model_id: str,
    cache_root: str | Path | None = None,
    output_root: str | Path = Path("."),
) -> InspectionResult:
    repo_id = normalize_model_id(model_id)
    output_root_path = Path(output_root)
    raw_dir = output_root_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    config_path = _download_repo_file(repo_id, CONFIG_FILENAME, cache_root)
    config_payload = _read_json_object(config_path)
    config = derive_opt_config(repo_id, config_payload)
    layer_index = select_middle_layer_index(config.num_hidden_layers)
    vram_ceiling_bytes = estimate_vram_ceiling_bytes(_detect_total_gpu_memory_bytes())
    model_constants = config.model_constants(layer_index, vram_ceiling_bytes)

    index_resolution = load_checkpoint_index(repo_id, cache_root)
    index_filename: str | None = None
    layer_prefix: str | None = None
    resolved_shard_filenames: tuple[str, ...] = ()
    resolved_shard_paths: tuple[Path, ...] = ()
    asset_source = ASSET_SOURCE_SYNTHETIC_FALLBACK
    asset_source_reason = "no_usable_index"
    synthetic_layer: dict[str, Any] | None = None

    if index_resolution is not None:
        index_filename, index_payload = index_resolution
        layer_prefix, resolved_shard_filenames = resolve_indexed_layer_shards(
            index_payload,
            layer_index,
        )
        if resolved_shard_filenames:
            resolved_shard_paths = _download_indexed_layer_shards(
                repo_id,
                resolved_shard_filenames,
                cache_root,
            )
            asset_source = ASSET_SOURCE_LAYER_SHARD
            asset_source_reason = "indexed_layer_shard"
        else:
            asset_source_reason = "index_missing_target_layer"
            synthetic_layer = build_synthetic_layer_metadata(
                config,
                layer_index,
                reason=asset_source_reason,
            )
    else:
        asset_source_reason = _determine_synthetic_fallback_reason(repo_id)
        synthetic_layer = build_synthetic_layer_metadata(
            config,
            layer_index,
            reason=asset_source_reason,
        )

    asset_manifest = {
        "model_id": repo_id,
        "asset_source": asset_source,
        "asset_source_reason": asset_source_reason,
        "config_filename": CONFIG_FILENAME,
        "index_filename": index_filename,
        "layer_index": layer_index,
        "layer_prefix": layer_prefix,
        "resolved_shard_filenames": list(resolved_shard_filenames),
        "resolved_shard_paths": [str(path) for path in resolved_shard_paths],
        "synthetic_layer": synthetic_layer,
    }

    model_constants_path = raw_dir / MODEL_CONSTANTS_FILENAME
    asset_manifest_path = raw_dir / ASSET_MANIFEST_FILENAME
    _write_json(model_constants_path, model_constants)
    _write_json(asset_manifest_path, asset_manifest)

    return InspectionResult(
        model_id=repo_id,
        output_root=output_root_path,
        model_constants_path=model_constants_path,
        asset_manifest_path=asset_manifest_path,
        model_constants=model_constants,
        asset_manifest=asset_manifest,
        asset_source=asset_source,
        resolved_shard_filenames=resolved_shard_filenames,
    )


def _download_repo_file(
    repo_id: str,
    filename: str,
    cache_root: str | Path | None = None,
) -> Path:
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=_cache_dir(cache_root),
        )
    )


def _try_download_repo_file(
    repo_id: str,
    filename: str,
    cache_root: str | Path | None = None,
) -> Path | None:
    try:
        return _download_repo_file(repo_id, filename, cache_root)
    except _MISSING_ENTRY_ERRORS:
        return None


def _download_indexed_layer_shards(
    repo_id: str,
    shard_filenames: Sequence[str],
    cache_root: str | Path | None = None,
) -> tuple[Path, ...]:
    snapshot_root = Path(
        snapshot_download(
            repo_id=repo_id,
            allow_patterns=list(shard_filenames),
            cache_dir=_cache_dir(cache_root),
        )
    )
    resolved_paths = tuple(snapshot_root / filename for filename in shard_filenames)
    missing_paths = [path for path in resolved_paths if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(
            "Layer shard download did not materialize expected file(s): "
            + ", ".join(str(path) for path in missing_paths)
        )
    return resolved_paths


def _determine_synthetic_fallback_reason(model_id: str) -> str:
    try:
        repo_files = set(_list_repo_files(model_id))
    except Exception:
        return "no_usable_index"
    if any(filename in repo_files for filename in MONOLITHIC_FILENAMES):
        return "monolithic_only"
    return "no_usable_index"


def _list_repo_files(model_id: str) -> tuple[str, ...]:
    return tuple(HfApi().list_repo_files(repo_id=model_id))


def _detect_total_gpu_memory_bytes(device_index: int = 0) -> int | None:
    try:
        import torch
    except ModuleNotFoundError:
        return None

    try:
        if not torch.cuda.is_available():
            return None
        device_properties = torch.cuda.get_device_properties(device_index)
        return int(device_properties.total_memory)
    except Exception:
        return None


def _synthetic_layer_parameter_shapes(
    config: OptConfig,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    hidden_size = config.hidden_size
    ffn_dim = config.ffn_dim
    return (
        ("self_attn.q_proj.weight", (hidden_size, hidden_size)),
        ("self_attn.q_proj.bias", (hidden_size,)),
        ("self_attn.k_proj.weight", (hidden_size, hidden_size)),
        ("self_attn.k_proj.bias", (hidden_size,)),
        ("self_attn.v_proj.weight", (hidden_size, hidden_size)),
        ("self_attn.v_proj.bias", (hidden_size,)),
        ("self_attn.out_proj.weight", (hidden_size, hidden_size)),
        ("self_attn.out_proj.bias", (hidden_size,)),
        ("self_attn_layer_norm.weight", (hidden_size,)),
        ("self_attn_layer_norm.bias", (hidden_size,)),
        ("fc1.weight", (ffn_dim, hidden_size)),
        ("fc1.bias", (ffn_dim,)),
        ("fc2.weight", (hidden_size, ffn_dim)),
        ("fc2.bias", (hidden_size,)),
        ("final_layer_norm.weight", (hidden_size,)),
        ("final_layer_norm.bias", (hidden_size,)),
    )


def _shape_numel(shape: Sequence[int]) -> int:
    product = 1
    for dimension in shape:
        product *= int(dimension)
    return product


def _cache_dir(cache_root: str | Path | None) -> Path | None:
    if cache_root is None:
        return None
    return Path(cache_root)


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


__all__ = [
    "ASSET_MANIFEST_FILENAME",
    "ASSET_SOURCE_LAYER_SHARD",
    "ASSET_SOURCE_SYNTHETIC_FALLBACK",
    "InspectionResult",
    "MODEL_CONSTANTS_FILENAME",
    "OptConfig",
    "build_synthetic_layer_metadata",
    "candidate_layer_prefixes",
    "derive_opt_config",
    "estimate_decoder_layer_weight_bytes_fp16",
    "estimate_total_weight_bytes_fp16",
    "estimate_vram_ceiling_bytes",
    "inspect_model",
    "load_checkpoint_index",
    "normalize_model_id",
    "resolve_indexed_layer_shards",
    "select_middle_layer_index",
]
