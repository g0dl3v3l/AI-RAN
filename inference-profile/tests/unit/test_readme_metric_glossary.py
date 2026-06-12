"""Test README metric glossary matches result schema."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README_PATH = REPO_ROOT / "README.md"


def test_readme_documents_prefill_metrics():
    """Verify README documents prefill profiling metrics."""
    with open(README_PATH) as f:
        readme_text = f.read()

    # Should mention prefill-related metrics
    assert "prefill" in readme_text.lower()
    assert "GEMM" in readme_text or "attention" in readme_text


def test_readme_documents_decode_metrics():
    """Verify README documents decode profiling metrics."""
    with open(README_PATH) as f:
        readme_text = f.read()

    # Should mention decode metrics and blockwise attention
    assert "decode" in readme_text.lower()
    assert "blockwise" in readme_text.lower() or "flash-decoding" in readme_text.lower()
    assert "attention_fetch_compute_us" in readme_text
    assert "reduction_overhead_us" in readme_text


def test_readme_documents_pcie_metrics():
    """Verify README documents PCIe metrics."""
    with open(README_PATH) as f:
        readme_text = f.read()

    # Should mention PCIe overlap
    assert "PCIe" in readme_text or "pcie" in readme_text.lower()
    assert "transfer_only_us" in readme_text
    assert "overlapped_us" in readme_text


def test_readme_defines_ttft():
    """Verify README defines ttft_ms metric."""
    with open(README_PATH) as f:
        readme_text = f.read()

    assert "ttft_ms" in readme_text
    # Should describe as time-to-first-token or similar
    ttft_section = readme_text[
        readme_text.find("ttft_ms") : readme_text.find("ttft_ms") + 200
    ]
    assert "time" in ttft_section.lower() or "token" in ttft_section.lower()


def test_readme_defines_tpot():
    """Verify README defines tpot_ms metrics."""
    with open(README_PATH) as f:
        readme_text = f.read()

    # Should mention both VRAM and PCIe variants
    assert "tpot_ms_vram" in readme_text
    assert "tpot_ms_pcie_async" in readme_text
    # Should describe as per-output-token
    assert (
        "per-output-token" in readme_text.lower() or "per-token" in readme_text.lower()
    )


def test_readme_defines_kv_metrics():
    """Verify README defines KV-cache related metrics."""
    with open(README_PATH) as f:
        readme_text = f.read()

    assert "survival_vram_bytes" in readme_text
    assert "decode_runway_bytes" in readme_text
    assert "kv_bytes_per_token_all_layers" in readme_text


def test_readme_vram_metric_definitions_match_remaining_headroom_formula() -> None:
    with open(README_PATH) as f:
        readme_text = f.read()

    survival_section = readme_text[
        readme_text.find("survival_vram_bytes") : readme_text.find(
            "survival_vram_bytes"
        )
        + 220
    ].lower()
    decode_section = readme_text[
        readme_text.find("decode_runway_bytes") : readme_text.find(
            "decode_runway_bytes"
        )
        + 220
    ].lower()

    assert "remaining" in survival_section
    assert "headroom" in survival_section
    assert "remaining" in decode_section
    assert "headroom" in decode_section


def test_readme_explains_blockwise_attention():
    """Verify README explains blockwise attention methodology."""
    with open(README_PATH) as f:
        readme_text = f.read()

    # Should explain block-wise approach
    blockwise_section = readme_text.lower()
    assert "block" in blockwise_section
    assert "attention" in blockwise_section


def test_readme_references_are_present():
    """Verify README includes academic references."""
    with open(README_PATH) as f:
        readme_text = f.read()

    # Should have References section
    assert "References" in readme_text or "references" in readme_text.lower()

    # Should mention FlashAttention and vLLM
    assert "FlashAttention" in readme_text or "arXiv" in readme_text
    assert "vLLM" in readme_text or "PagedAttention" in readme_text


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
