"""Offline, noneditable wheel and installed console-script calibration contracts.

Prepare KVSCOPE_TEST_WHEELHOUSE before pytest; this suite never downloads, skips,
or reuses the source environment as the installed environment.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import tomllib
import venv
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]
SECRET = "calibration-install-secret-must-not-be-retained"


def _python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@dataclass(frozen=True)
class InstalledPackage:
    """The isolated installed CLI/filesystem seam, with saved execution evidence."""

    prefix: Path
    cwd: Path
    environment: dict[str, str] = dataclass_field(repr=False)

    @property
    def python(self) -> Path:
        return _python(self.prefix)

    @property
    def cli(self) -> Path:
        return self.prefix / (
            "Scripts/kvscope.exe" if os.name == "nt" else "bin/kvscope"
        )

    def run(
        self, argv: list[str], name: str, *, expected: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            argv,
            cwd=self.cwd,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        (self.cwd / f"{name}.stdout").write_text(result.stdout, encoding="utf-8")
        (self.cwd / f"{name}.stderr").write_text(result.stderr, encoding="utf-8")
        (self.cwd / f"{name}.exit").write_text(str(result.returncode), encoding="utf-8")
        assert result.returncode == expected, result.stdout + result.stderr
        return result

    def command(
        self, args: list[str], name: str, *, expected: int = 0
    ) -> dict[str, Any]:
        result = self.run([str(self.cli), *args], name, expected=expected)
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        return data


def _digests(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(directory.rglob("*.json"))
    }


@pytest.fixture(scope="session")
def installed_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[InstalledPackage]:
    """Build and install only local wheels into two fresh, non-system venvs."""
    configured = os.environ.get("KVSCOPE_TEST_WHEELHOUSE")
    assert configured, (
        "Prepare dependency wheels before pytest: set KVSCOPE_TEST_WHEELHOUSE and run "
        "python tools/prepare_calibration_install_wheels.py "
        '--wheelhouse "$KVSCOPE_TEST_WHEELHOUSE"'
    )
    wheelhouse = Path(configured).resolve()
    assert wheelhouse.is_dir(), f"Missing offline wheelhouse: {wheelhouse}"
    area = tmp_path_factory.mktemp("calibration-install")
    cwd = area / "outside-source"
    cwd.mkdir()
    assert not cwd.is_relative_to(ROOT)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "PATH",
            "HOME",
            "TMPDIR",
            "TEMP",
            "TMP",
            "SYSTEMROOT",
            "WINDIR",
            "LANG",
            "LC_ALL",
        }
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONSAFEPATH="1",
        PIP_CONFIG_FILE=os.devnull,
        PIP_NO_INDEX="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        HTTP_PROXY="http://127.0.0.1:9",
        HTTPS_PROXY="http://127.0.0.1:9",
        KVSCOPE_INSTALL_SECRET=SECRET,
    )
    build = area / "build-env"
    install = area / "install-env"
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(build)
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(install)
    package = InstalledPackage(install, cwd, environment)
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package.run(
        [
            str(_python(build)),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            *manifest["build-system"]["requires"],
            "wheel",
        ],
        "build-dependencies",
    )
    wheels = area / "wheels"
    package.run(
        [
            str(_python(build)),
            "-m",
            "pip",
            "wheel",
            str(ROOT),
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
        ],
        "wheel-build",
    )
    artifacts = list(wheels.glob("kvscope-*.whl"))
    assert len(artifacts) == 1
    package.run(
        [
            str(package.python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            str(artifacts[0]),
        ],
        "wheel-install",
    )
    package.run([str(package.python), "-m", "pip", "check"], "pip-check")
    before = _digests(install / "share/kvscope/profiles")
    assert before == _digests(ROOT / "profiles") and before
    _write(cwd / "profiles-before.json", before)
    yield package
    after = _digests(install / "share/kvscope/profiles")
    _write(cwd / "profiles-after.json", after)
    assert after == before


@pytest.fixture(scope="session")
def installed_schemas(installed_package: InstalledPackage) -> dict[str, Any]:
    """Read assets through the installed package, never through source fallback."""
    code = """
import importlib.metadata as md, importlib.resources as resources
import importlib.util, json, pathlib, sys
import kvscope
from kvscope.calibration.artifacts import CALIBRATION_ARTIFACTS
from kvscope.resources import default_profile_directory
prefix = pathlib.Path(sys.prefix).resolve()
module = pathlib.Path(kvscope.__file__).resolve()
assert module.is_relative_to(prefix) and 'site-packages' in module.parts
url = json.loads(md.distribution('kvscope').read_text('direct_url.json'))
assert 'archive_info' in url and not url.get('dir_info', {}).get('editable', False)
profiles = {
    c: str(default_profile_directory(c).resolve())
    for c in ['models','hardware','backends']
}
for path in profiles.values():
    assert pathlib.Path(path).is_relative_to(prefix / 'share/kvscope/profiles')
    assert list(pathlib.Path(path).glob('*.json'))
schemas = {
    a.name: json.loads(resources.files('kvscope').joinpath(
        'schemas', a.schema_filename).read_text())
    for a in CALIBRATION_ARTIFACTS
}
for name in ['jsonschema','torch','transformers','vllm','huggingface_hub']:
    assert importlib.util.find_spec(name) is None
assert 'jsonschema' not in sys.modules
print(json.dumps({'module':str(module),'profiles':profiles,'schemas':schemas,'requires':md.requires('kvscope')}))
"""
    package = installed_package
    probe = json.loads(
        package.run([str(package.python), "-c", code], "installed-resources").stdout
    )
    assert len(probe["schemas"]) == 7
    for schema in probe["schemas"].values():
        Draft202012Validator.check_schema(schema)
    runtime = [r for r in probe["requires"] if "extra ==" not in r]
    assert {Requirement(r).name for r in runtime} == {"packaging", "pydantic"}
    return probe["schemas"]


def test_installed_console_script_and_resources(
    installed_package: InstalledPackage, installed_schemas: dict[str, Any]
) -> None:
    """A declared-dependencies-only wheel starts and owns all built-in resources."""
    package = installed_package
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert (
        package.run([str(package.cli), "--version"], "version").stdout.strip()
        == f"kvscope {version}"
    )
    assert "calibrate" in package.run([str(package.cli), "--help"], "help").stdout
    assert installed_schemas["run_manifest"] != installed_schemas["run_result"]


def _validate(schemas: dict[str, Any], kind: str, value: object) -> None:
    Draft202012Validator(schemas[kind], format_checker=FormatChecker()).validate(value)


@dataclass(frozen=True)
class CalibrationChain:
    """Actual installed outputs, also used as independent schema/loader samples."""

    package: InstalledPackage
    config_path: Path
    report: dict[str, Any]
    report_path: Path
    manifest: dict[str, Any]
    manifest_path: Path
    run: dict[str, Any]
    comparison_paths: list[Path]
    instances: dict[str, dict[str, Any]]


def _analyze(
    package: InstalledPackage, config: Path, name: str, context: int = 64
) -> dict[str, Any]:
    return package.command(
        [
            "analyze",
            str(config),
            "--offline",
            "--hardware",
            "generic-discrete-16gib",
            "--backend",
            "vllm-generic-unverified-v0",
            "--backend-version",
            "0.6.6",
            "--context",
            str(context),
            "--format",
            "json",
        ],
        name,
    )


@pytest.fixture(scope="session")
def calibration_chain(
    installed_package: InstalledPackage, installed_schemas: dict[str, Any]
) -> CalibrationChain:
    """Real analyze → repeated runner/export → compare×3 → fit → accepted review."""
    package = installed_package
    config = _write(
        package.cwd / "tiny-config.json",
        {
            "model_type": "llama",
            "architectures": ["LlamaForCausalLM"],
            "num_hidden_layers": 2,
            "hidden_size": 128,
            "num_attention_heads": 4,
            "num_key_value_heads": 2,
            "max_position_embeddings": 512,
            "vocab_size": 256,
            "parameter_count": 1000,
        },
    )
    report = _analyze(package, config, "analyze")
    report_path = _write(package.cwd / "report.json", report)
    provenance = report["provenance"]
    assert provenance["model_config_digest"]
    expected = report["aggregation"]["total_requirement"]["expected_bytes"]
    assert type(expected) is int and expected > 0
    # Use actual provenance; do not fabricate verified comparison facts.
    template = {
        **provenance,
        "record_id_prefix": "installed-record",
        "confidence": "high",
        "measurement_source": "local Python",
        "measurement_method": "observation JSON",
        "notes": None,
    }
    code = f"""
import json, os, pathlib, sys
counter = pathlib.Path('counter.txt')
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))
print(os.environ['KVSCOPE_INSTALL_SECRET'])
print(os.environ['KVSCOPE_INSTALL_SECRET'], file=sys.stderr)
observation = {{'schema_version':'v0.1','observation_id':'obs-'+str(n),
    'observed_at':'2025-01-15T12:00:00Z',
    'observed_peak_memory_bytes':{expected} + [10,30,60][(n-1)%3],
    'evidence':[{{'evidence_id':'obs-'+str(n), 'source_type':'local_measurement',
        'source':'test observer'}}], 'notes': None}}
pathlib.Path(os.environ['KVSCOPE_OBSERVATION_PATH']).write_text(json.dumps(observation))
"""
    manifest = {
        "schema_version": "v0.1",
        "run_id": "installed-run",
        "command": [str(package.python), "-c", code],
        "observation_json_path": "observation.json",
        "repetitions": 3,
        "timeout_seconds": 10,
        "working_directory": None,
        "notes": None,
        "inherit_environment": False,
        "environment_names": ["KVSCOPE_INSTALL_SECRET"],
        "measurement": template,
    }
    manifest_path = _write(package.cwd / "manifest.json", manifest)
    _validate(installed_schemas, "run_manifest", manifest)
    run = package.command(
        [
            "calibrate",
            "run",
            "--manifest-json",
            str(manifest_path),
            "--output-dir",
            "measurements",
            "--format",
            "json",
        ],
        "run",
    )
    _validate(installed_schemas, "run_result", run)
    assert len(run["successful_measurements"]) == 3 and not run["failures"]
    assert run["conservative_peak_memory_bytes"] == expected + 60
    assert run["selected_measurement_id"] == "installed-record-3"
    assert SECRET not in json.dumps(run) and code not in json.dumps(run)
    records = [
        json.loads(Path(path).read_text()) for path in run["exported_measurement_paths"]
    ]
    assert records == run["successful_measurements"]
    comparisons = []
    paths = []
    for index, (path, record) in enumerate(
        zip(run["exported_measurement_paths"], records, strict=True)
    ):
        _validate(installed_schemas, "measurement", record)
        comparison = package.command(
            [
                "calibrate",
                "compare",
                "--report-json",
                str(report_path),
                "--measurement-json",
                path,
                "--format",
                "json",
            ],
            f"compare-{index}",
        )
        assert (
            comparison["status"] == "comparable"
            and comparison["identity_verification"] == "verified"
        )
        _validate(installed_schemas, "comparison", comparison)
        comparisons.append(comparison)
        paths.append(_write(package.cwd / f"comparison-{index}.json", comparison))
    fit_args = [arg for path in paths for arg in ["--comparison-json", str(path)]]
    candidate = package.command(
        ["calibrate", "fit", *fit_args, "--format", "json"], "fit"
    )
    _validate(installed_schemas, "profile_candidate", candidate)
    assert candidate["status"] == "scoped_envelope" and candidate["sample_count"] == 3
    assert candidate["comparison_record_ids"] == [r["record_id"] for r in records]
    assert candidate["additional_reserve_bytes"] == {
        "lower_bytes": 10,
        "expected_bytes": 30,
        "upper_bytes": 60,
    }
    candidate_path = _write(package.cwd / "candidate.json", candidate)
    review = package.command(
        [
            "calibrate",
            "review",
            "--candidate-json",
            str(candidate_path),
            "--reviewer",
            "installed-test",
            "--decision",
            "accepted",
            "--notes",
            "Three local observations",
            "--format",
            "json",
        ],
        "review",
    )
    _validate(installed_schemas, "review_decision", review)
    assert (
        review["status"] == "accepted"
        and review["candidate_id"] == candidate["candidate_id"]
    )
    facts = {k: v for k, v in candidate.items() if k not in {"kind", "candidate_id"}}
    digest = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    assert review["candidate_digest"] == digest
    observation = json.loads((package.cwd / "observation.json").read_text())
    _validate(installed_schemas, "observation", observation)
    instances = {
        "measurement": records[0],
        "run_manifest": manifest,
        "observation": observation,
        "comparison": comparisons[0],
        "run_result": run,
        "profile_candidate": candidate,
        "review_decision": review,
    }
    return CalibrationChain(
        package,
        config,
        report,
        report_path,
        manifest,
        manifest_path,
        run,
        paths,
        instances,
    )


def test_installed_calibration_chain(calibration_chain: CalibrationChain) -> None:
    """Installed public CLI outputs include a digest-bound review."""
    assert len(calibration_chain.instances) == 7


def test_installed_export_does_not_overwrite(
    calibration_chain: CalibrationChain,
) -> None:
    """A second real run cannot replace any of the previously exported records."""
    chain = calibration_chain
    before = _digests(chain.package.cwd / "measurements")
    result = chain.package.run(
        [
            str(chain.package.cli),
            "calibrate",
            "run",
            "--manifest-json",
            str(chain.manifest_path),
            "--output-dir",
            "measurements",
            "--format",
            "json",
        ],
        "overwrite",
        expected=2,
    )
    assert "would overwrite" in result.stderr
    assert _digests(chain.package.cwd / "measurements") == before


@pytest.mark.parametrize("field", ["repetitions", "schema_version"])
def test_invalid_installed_manifest_never_executes(
    calibration_chain: CalibrationChain, field: str
) -> None:
    """Manifest validation rejects input before a command can write its sentinel."""
    chain = calibration_chain
    sentinel = chain.package.cwd / f"must-not-run-{field}"
    bad = copy.deepcopy(chain.manifest)
    bad["command"] = [
        str(chain.package.python),
        "-c",
        f"from pathlib import Path;Path({str(sentinel)!r}).touch()",
    ]
    bad[field] = 0 if field == "repetitions" else "v9.9"
    path = _write(chain.package.cwd / f"invalid-manifest-{field}.json", bad)
    chain.package.run(
        [str(chain.package.cli), "calibrate", "run", "--manifest-json", str(path)],
        f"invalid-manifest-{field}",
        expected=2,
    )
    assert not sentinel.exists()


@pytest.mark.parametrize("mode", ["mixed", "nonzero", "missing", "timeout"])
def test_installed_runner_failure_contracts(
    calibration_chain: CalibrationChain, installed_schemas: dict[str, Any], mode: str
) -> None:
    """Mixed runs select only successes; failed runs have no measurement conclusion."""
    chain = calibration_chain
    manifest = copy.deepcopy(chain.manifest)
    manifest["run_id"] = mode
    manifest["observation_json_path"] = mode + "-observation.json"
    if mode == "mixed":
        # Successful samples 1 and 3 keep their true IDs, while sample 2 fails.
        code = chain.manifest["command"][2].replace("counter.txt", "mixed-counter.txt")
        code += "\nraise SystemExit(7) if n == 2 else SystemExit(0)\n"
    elif mode == "nonzero":
        code = (
            "import os,sys;print(os.environ['KVSCOPE_INSTALL_SECRET']);"
            "raise SystemExit(7)"
        )
    elif mode == "missing":
        code = "pass"
    else:
        code = "import time;time.sleep(5)"
        manifest["timeout_seconds"] = 1
    manifest["command"] = [str(chain.package.python), "-c", code]
    path = _write(chain.package.cwd / f"{mode}-manifest.json", manifest)
    result = chain.package.command(
        ["calibrate", "run", "--manifest-json", str(path), "--format", "json"],
        "failure-" + mode,
        expected=0 if mode == "mixed" else 3,
    )
    _validate(installed_schemas, "run_result", result)
    assert SECRET not in json.dumps(result) and code not in json.dumps(result)
    if mode == "mixed":
        assert (
            len(result["successful_measurements"]) == 2 and len(result["failures"]) == 1
        )
        assert result["selected_measurement_id"] == "installed-record-3"
        assert result["failures"][0]["sample_index"] == 2
    else:
        assert not result["successful_measurements"]
        assert (
            result["conservative_peak_memory_bytes"] is None
            and result["selected_measurement_id"] is None
        )
        expected_code = {
            "nonzero": "command_nonzero_exit",
            "missing": "observation_missing",
            "timeout": "command_timeout",
        }[mode]
        assert len(result["failures"]) == 3 and all(
            f["code"] == expected_code for f in result["failures"]
        )


@pytest.mark.parametrize(
    "mode", ["partial", "mismatch", "unavailable", "incomplete", "negative"]
)
def test_installed_comparison_states(
    calibration_chain: CalibrationChain, installed_schemas: dict[str, Any], mode: str
) -> None:
    """Nullable/error states remain schema-valid; unverified input cannot be fitted."""
    chain = calibration_chain
    report = copy.deepcopy(chain.report)
    measurement = copy.deepcopy(chain.instances["measurement"])
    exit_code = 0
    if mode == "partial":
        measurement.update(backend_version=None, confidence="medium")
    elif mode == "mismatch":
        measurement["model_id"] = "different-model"
        exit_code = 3
    elif mode == "unavailable":
        report["provenance"] = None
        exit_code = 3
    elif mode == "incomplete":
        report["aggregation"].update(
            total_requirement=None,
            is_partial=True,
            missing_components=["runtime_overhead"],
            confidence="unknown",
        )
        report["feasibility"].update(
            requirement=None,
            internal_status="unknown",
            product_status="unknown",
            is_actionable=False,
            confidence="unknown",
        )
        exit_code = 3
    else:
        measurement["observed_peak_memory_bytes"] = (
            report["aggregation"]["total_requirement"]["expected_bytes"] - 1
        )
    report_path = _write(chain.package.cwd / f"{mode}-report.json", report)
    measurement_path = _write(
        chain.package.cwd / f"{mode}-measurement.json", measurement
    )
    comparison = chain.package.command(
        [
            "calibrate",
            "compare",
            "--report-json",
            str(report_path),
            "--measurement-json",
            str(measurement_path),
            "--format",
            "json",
        ],
        "state-" + mode,
        expected=exit_code,
    )
    _validate(installed_schemas, "comparison", comparison)
    expected_identity = {
        "partial": "partial",
        "mismatch": "mismatch",
        "unavailable": "unavailable",
        "incomplete": "verified",
        "negative": "verified",
    }[mode]
    assert comparison["identity_verification"] == expected_identity
    if mode == "negative":
        assert comparison["delta_vs_expected_bytes"] == -1
        return
    path = _write(chain.package.cwd / f"{mode}-comparison.json", comparison)
    rejection = chain.package.run(
        [
            str(chain.package.cli),
            "calibrate",
            "fit",
            "--comparison-json",
            str(path),
            "--format",
            "json",
        ],
        "reject-fit-" + mode,
        expected=2,
    )
    assert (
        "not identity verified" in rejection.stderr
        if mode == "partial"
        else "not comparable" in rejection.stderr
    )


def test_installed_fit_rejects_different_verified_scopes(
    calibration_chain: CalibrationChain,
) -> None:
    """Individually verified comparisons cannot loosen the exact fitting scope."""
    chain = calibration_chain
    report = _analyze(
        chain.package, chain.config_path, "other-scope-analyze", context=128
    )
    measurement = copy.deepcopy(chain.instances["measurement"])
    measurement["inference_config"] = report["provenance"]["inference_config"]
    measurement["observed_peak_memory_bytes"] = (
        report["aggregation"]["total_requirement"]["expected_bytes"] + 10
    )
    report_path = _write(chain.package.cwd / "other-scope-report.json", report)
    record_path = _write(chain.package.cwd / "other-scope-record.json", measurement)
    comparison = chain.package.command(
        [
            "calibrate",
            "compare",
            "--report-json",
            str(report_path),
            "--measurement-json",
            str(record_path),
            "--format",
            "json",
        ],
        "other-scope-compare",
    )
    assert comparison["identity_verification"] == "verified"
    path = _write(chain.package.cwd / "other-scope-comparison.json", comparison)
    rejection = chain.package.run(
        [
            str(chain.package.cli),
            "calibrate",
            "fit",
            "--comparison-json",
            str(path),
            "--comparison-json",
            str(chain.comparison_paths[0]),
        ],
        "other-scope-fit",
        expected=2,
    )
    assert "identical verified calibration scope" in rejection.stderr


def test_installed_insufficient_candidate_cannot_be_accepted(
    calibration_chain: CalibrationChain, installed_schemas: dict[str, Any]
) -> None:
    chain = calibration_chain
    candidate = chain.package.command(
        [
            "calibrate",
            "fit",
            "--comparison-json",
            str(chain.comparison_paths[0]),
            "--format",
            "json",
        ],
        "insufficient-fit",
        expected=3,
    )
    assert candidate["status"] == "insufficient_data"
    _validate(installed_schemas, "profile_candidate", candidate)
    path = _write(chain.package.cwd / "insufficient-candidate.json", candidate)
    args = [
        "calibrate",
        "review",
        "--candidate-json",
        str(path),
        "--reviewer",
        "test",
        "--notes",
        "Not enough samples",
        "--format",
        "json",
    ]
    rejected = chain.package.command(
        [*args, "--decision", "rejected"], "rejected-review"
    )
    _validate(installed_schemas, "review_decision", rejected)
    assert rejected["status"] == "rejected"
    result = chain.package.run(
        [str(chain.package.cli), *args, "--decision", "accepted"],
        "insufficient-accept",
        expected=2,
    )
    assert "insufficient-data candidates cannot be accepted" in result.stderr


@pytest.mark.parametrize("kind", ["comparison", "profile_candidate"])
@pytest.mark.parametrize("field", ["kind", "schema_version"])
def test_installed_loader_rejects_wrong_envelopes(
    calibration_chain: CalibrationChain, kind: str, field: str
) -> None:
    chain = calibration_chain
    bad = copy.deepcopy(chain.instances[kind])
    bad[field] = "wrong"
    path = _write(chain.package.cwd / f"bad-{kind}-{field}.json", bad)
    args = (
        ["calibrate", "fit", "--comparison-json", str(path)]
        if kind == "comparison"
        else [
            "calibrate",
            "review",
            "--candidate-json",
            str(path),
            "--reviewer",
            "test",
            "--decision",
            "accepted",
            "--notes",
            "test",
        ]
    )
    chain.package.run(
        [str(chain.package.cli), *args], f"bad-{kind}-{field}", expected=2
    )


@pytest.mark.parametrize("kind", ["comparison", "profile_candidate"])
@pytest.mark.parametrize("null_kind", [False, True])
def test_installed_legacy_loader_compatibility(
    calibration_chain: CalibrationChain, kind: str, null_kind: bool
) -> None:
    chain = calibration_chain
    bare = copy.deepcopy(chain.instances[kind])
    bare.pop("kind")
    if null_kind:
        bare["kind"] = None
    path = _write(chain.package.cwd / f"legacy-{kind}-{null_kind}.json", bare)
    if kind == "comparison":
        result = chain.package.command(
            ["calibrate", "fit", "--comparison-json", str(path), "--format", "json"],
            f"legacy-{kind}-{null_kind}",
            expected=3,
        )
        assert result["status"] == "insufficient_data"
    else:
        result = chain.package.command(
            [
                "calibrate",
                "review",
                "--candidate-json",
                str(path),
                "--reviewer",
                "test",
                "--decision",
                "accepted",
                "--notes",
                "Legacy compatibility",
                "--format",
                "json",
            ],
            f"legacy-{kind}-{null_kind}",
        )
        assert result["status"] == "accepted"


@pytest.mark.parametrize("mutation", ["version", "kind", "extra", "type"])
def test_installed_schemas_reject_invalid_envelopes(
    calibration_chain: CalibrationChain,
    installed_schemas: dict[str, Any],
    mutation: str,
) -> None:
    for kind, instance in calibration_chain.instances.items():
        sample = copy.deepcopy(instance)
        sample[
            {
                "version": "schema_version",
                "kind": "kind",
                "extra": "unexpected",
                "type": "schema_version",
            }[mutation]
        ] = 123 if mutation == "type" else "wrong"
        with pytest.raises(ValidationError):
            _validate(installed_schemas, kind, sample)


def test_installed_schemas_reject_nested_bounds_and_types(
    calibration_chain: CalibrationChain, installed_schemas: dict[str, Any]
) -> None:
    for kind in ["measurement", "observation"]:
        for field, value in [
            ("observed_peak_memory_bytes", 0),
            ("observed_peak_memory_bytes", "250"),
            ("evidence", []),
        ]:
            sample = copy.deepcopy(calibration_chain.instances[kind])
            sample[field] = value
            with pytest.raises(ValidationError):
                _validate(installed_schemas, kind, sample)
    for kind in [
        "measurement",
        "run_manifest",
        "comparison",
        "profile_candidate",
        "run_result",
    ]:
        sample = copy.deepcopy(calibration_chain.instances[kind])
        if kind == "measurement":
            config = sample["inference_config"]
        elif kind in {"run_manifest", "comparison"}:
            config = sample["measurement"]["inference_config"]
        elif kind == "profile_candidate":
            config = sample["scope"]["inference_config"]
        else:
            config = sample["successful_measurements"][0]["inference_config"]
        config["active_sequences"] = 0
        with pytest.raises(ValidationError):
            _validate(installed_schemas, kind, sample)
    sample = copy.deepcopy(calibration_chain.instances["review_decision"])
    sample["status"] = "not-a-decision"
    with pytest.raises(ValidationError):
        _validate(installed_schemas, "review_decision", sample)
