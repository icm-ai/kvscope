"""Unit tests for kvscope assess-memory CLI subcommand."""

import json

from kvscope.cli.app import main


def test_cli_assess_memory(tmp_path):
    weights_file = tmp_path / "weights.json"
    kv_file = tmp_path / "kv.json"
    overhead_file = tmp_path / "overhead.json"
    budget_file = tmp_path / "budget.json"

    weights_json = {
        "quantized_payload_bytes": 4000,
        "unquantized_payload_bytes": 0,
        "scale_overhead_bytes": 0,
        "zero_point_overhead_bytes": 0,
        "metadata_bytes": 0,
        "alignment_overhead_bytes": 0,
        "total_bytes": 4000,
        "effective_bits_per_weight": "16/1",
        "estimation_method": "parameter_count",
        "confidence": "exact",
        "assumptions": [],
        "warnings": [],
        "estimated_resident_weight_bytes": 4000,
    }
    weights_file.write_text(json.dumps(weights_json), encoding="utf-8")

    kv_json = {
        "formula_inputs": {
            "num_hidden_layers": 32,
            "num_attention_heads": 32,
            "num_key_value_heads": 8,
            "head_dim": 128,
            "context_tokens": 4096,
            "prefix_tokens": 0,
            "multimodal_tokens": 0,
            "active_sequences": 1,
            "kv_dtype": "fp16",
            "bytes_per_element": 2,
            "block_size": 16,
            "active_sequences_source": "equal",
            "prefix_shared": False,
        },
        "raw_bytes": 2000,
        "allocated_bytes": 2000,
        "alignment_waste_bytes": 0,
        "bytes_per_token": 256,
        "bytes_per_sequence": 1048576,
    }
    kv_file.write_text(json.dumps(kv_json), encoding="utf-8")

    overhead_json = {
        "base_runtime": {"lower_bytes": 500, "expected_bytes": 500, "upper_bytes": 500},
        "parameter_scaled_overhead": {
            "lower_bytes": 200,
            "expected_bytes": 200,
            "upper_bytes": 200,
        },
        "workspace": {
            "lower_bytes": 300,
            "expected_bytes": 300,
            "upper_bytes": 300,
        },
        "graph_capture": {"lower_bytes": 0, "expected_bytes": 0, "upper_bytes": 0},
        "backend_buffers": {
            "lower_bytes": 200,
            "expected_bytes": 200,
            "upper_bytes": 200,
        },
        "allocator_margin": {
            "lower_bytes": 300,
            "expected_bytes": 300,
            "upper_bytes": 300,
        },
        "subtotal_before_allocator_margin": {
            "lower_bytes": 1200,
            "expected_bytes": 1200,
            "upper_bytes": 1200,
        },
        "total_runtime_overhead": {
            "lower_bytes": 1000,
            "expected_bytes": 1500,
            "upper_bytes": 2000,
        },
        "backend_profile_id": "vllm_v0",
        "backend_version_specifier": ">=0.4.0",
        "hardware_profile_id": "rtx_4090",
        "confidence": "high",
        "is_partial": False,
        "missing_components": [],
        "assumptions": [],
        "warnings": [],
        "evidence": [],
    }
    overhead_file.write_text(json.dumps(overhead_json), encoding="utf-8")

    budget_json = {
        "physical_total_bytes": 16000,
        "os_reserve": {
            "lower_bytes": 2000,
            "expected_bytes": 2000,
            "upper_bytes": 2000,
        },
        "display_reserve": {"lower_bytes": 0, "expected_bytes": 0, "upper_bytes": 0},
        "background_process_reserve": {
            "lower_bytes": 0,
            "expected_bytes": 0,
            "upper_bytes": 0,
        },
        "device_specific_reserve": {
            "lower_bytes": 0,
            "expected_bytes": 0,
            "upper_bytes": 0,
        },
        "user_reserve": {"lower_bytes": 0, "expected_bytes": 0, "upper_bytes": 0},
        "total_non_model_reserve": {
            "lower_bytes": 2000,
            "expected_bytes": 2000,
            "upper_bytes": 2000,
        },
        "allocatable_before_headroom": {
            "lower_bytes": 14000,
            "expected_bytes": 14000,
            "upper_bytes": 14000,
        },
        "recommended_headroom": {
            "lower_bytes": 2000,
            "expected_bytes": 2000,
            "upper_bytes": 2000,
        },
        "recommended_allocatable": {
            "lower_bytes": 12000,
            "expected_bytes": 12000,
            "upper_bytes": 12000,
        },
        "memory_topology": "discrete",
        "confidence": "high",
        "assumptions": [],
        "warnings": [],
    }
    budget_file.write_text(json.dumps(budget_json), encoding="utf-8")

    exit_code = main(
        [
            "assess-memory",
            "--weights-json",
            str(weights_file),
            "--kv-cache-json",
            str(kv_file),
            "--runtime-overhead-json",
            str(overhead_file),
            "--hardware-budget-json",
            str(budget_file),
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
