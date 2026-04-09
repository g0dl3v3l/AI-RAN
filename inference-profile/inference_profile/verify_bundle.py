"""Verify run bundle completeness and checksums."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Required files for a complete bundle
REQUIRED_BUNDLE_FILES = {
    "run_manifest.json": "manifest metadata",
    "raw/prefill_events.csv": "raw prefill profiling events",
    "raw/decode_events.csv": "raw decode profiling events",
    "raw/pcie_events.csv": "raw PCIe profiling events",
    "derived/prefill_summary.csv": "derived prefill summary",
    "derived/decode_summary.csv": "derived decode summary",
    "derived/pcie_summary.csv": "derived PCIe summary",
}


def compute_file_checksum(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute checksum of a file."""
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_bundle_complete(run_root: Path) -> dict[str, bool]:
    """
    Verify all required files exist in bundle.
    
    Returns:
        dict: Mapping of file paths to presence (True/False)
    """
    run_root = Path(run_root)
    results = {}
    
    for rel_path in REQUIRED_BUNDLE_FILES:
        full_path = run_root / rel_path
        results[rel_path] = full_path.exists()
        if not results[rel_path]:
            logger.warning(f"Missing required file: {rel_path}")
    
    return results


def verify_checksums(run_root: Path) -> dict[str, dict]:
    """
    Verify checksums of bundle files if checksums file exists.
    
    Returns:
        dict: Mapping of file paths to checksum verification results
              {"computed": "...", "expected": "...", "match": True/False}
    """
    run_root = Path(run_root)
    checksums_file = run_root / "checksums" / "checksums.json"
    
    if not checksums_file.exists():
        logger.info("No checksums file found, skipping checksum verification")
        return {}
    
    with open(checksums_file, "r") as f:
        expected_checksums = json.load(f)
    
    results = {}
    for file_path_rel, expected_sha256 in expected_checksums.items():
        full_path = run_root / file_path_rel
        
        if not full_path.exists():
            results[file_path_rel] = {
                "computed": None,
                "expected": expected_sha256,
                "match": False,
                "reason": "file not found",
            }
            continue
        
        computed_sha256 = compute_file_checksum(full_path)
        match = computed_sha256 == expected_sha256
        
        results[file_path_rel] = {
            "computed": computed_sha256,
            "expected": expected_sha256,
            "match": match,
        }
        
        if not match:
            logger.warning(f"Checksum mismatch for {file_path_rel}")
    
    return results


def verify_bundle(run_root: Path) -> dict:
    """
    Full bundle verification: completeness + checksums.
    
    Returns:
        dict with keys:
            "complete": bool - all required files present
            "completeness_results": dict - per-file presence
            "checksums_valid": bool - all checksums match (if present)
            "checksum_results": dict - per-file checksum results
            "status": "success" | "fetch_failed"
    """
    run_root = Path(run_root)
    
    # Check completeness
    completeness_results = verify_bundle_complete(run_root)
    complete = all(completeness_results.values())
    
    # Check checksums
    checksum_results = verify_checksums(run_root)
    checksums_valid = all(r.get("match", True) for r in checksum_results.values())
    
    status = "success" if (complete and checksums_valid) else "fetch_failed"
    
    return {
        "complete": complete,
        "completeness_results": completeness_results,
        "checksums_valid": checksums_valid,
        "checksum_results": checksum_results,
        "status": status,
    }
