"""Offline validation and deterministic execution for the Plan-A registry.

This module has no provider, network, label, or scoring access.  It validates
the pre-seal architecture contract and executes only already-frozen local
selection, action, and aggregation rules.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import Any, Mapping, Sequence

from .canonical import canonical_sha256, strict_json_loads


class ArchitectureRegistryError(ValueError):
    """Raised when a registry or typed architecture artifact is inconsistent."""


REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "refine-logs"
    / "PLAN_A_ARCHITECTURE_REGISTRY.json"
)

_CANDIDATES = (
    "A01-HIER-VERIFY-4H",
    "A02-PAR-DEBATE-4X",
    "A03-TYPED-ROUTE-4X",
)

_ROUTES: dict[str, tuple[str, str, tuple[tuple[str, str], ...]]] = {
    "R00_DEFAULT_N0_GLOBAL": (
        "local_route_default",
        "LOCAL_DEFAULT_AFTER_W1_FAILURE",
        (
            ("w2_trend_specialist", "T_DEFAULT_N0_GLOBAL"),
            ("w3_uncertainty_specialist", "U_DEFAULT_N0_GLOBAL"),
        ),
    ),
    "R01_PERSISTENCE_DRIFT_BASE_INTERVALS": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_PERSISTENCE_DRIFT"),
            ("w3_uncertainty_specialist", "U_BASE_INTERVALS"),
        ),
    ),
    "R02_LOCAL_SHAPE_BASE_INTERVALS": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_LOCAL_SHAPE"),
            ("w3_uncertainty_specialist", "U_BASE_INTERVALS"),
        ),
    ),
    "R03_STATE_SPACE_ROBUST_INTERVALS": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_STATE_SPACE_REGRESSION"),
            ("w3_uncertainty_specialist", "U_ROBUST_INTERVALS"),
        ),
    ),
    "R04_TREND_FUSION_INTERVAL_FUSION": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_TREND_FUSIONS"),
            ("w3_uncertainty_specialist", "U_INTERVAL_FUSIONS"),
        ),
    ),
    "R05_ROBUST_FUSION_CALIBRATION": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_TREND_FUSIONS"),
            ("w3_uncertainty_specialist", "U_CALIBRATION"),
        ),
    ),
    "R06_LOCATION_CORRECTION_CALIBRATION": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_LOCATION_CORRECTION"),
            ("w3_uncertainty_specialist", "U_CALIBRATION"),
        ),
    ),
    "R07_FULL_ACTION_BALANCED": (
        "w1_typed_router",
        "PROVIDER_ROUTER",
        (
            ("w2_trend_specialist", "T_ALL_LOCATION_ACTIONS"),
            ("w3_uncertainty_specialist", "U_ALL_UNCERTAINTY_ACTIONS"),
        ),
    ),
}

_DECISIONS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "A01_SELECT_W1": (_CANDIDATES[0], "w4_arbiter", "AGG_NONE_SELECT_PARENT", ("w1",)),
    "A01_SELECT_W2": (_CANDIDATES[0], "w4_arbiter", "AGG_NONE_SELECT_PARENT", ("w2",)),
    "A01_MEDIAN_W1_W2_N0": (
        _CANDIDATES[0], "w4_arbiter", "AGG_COMPONENTWISE_MEDIAN_W1_W2_N0", ("w1", "w2", "N0")
    ),
    "A01_DELIBERATE_FALLBACK": (_CANDIDATES[0], "w4_arbiter", "AGG_COMMON_FALLBACK", ("N0",)),
    "A02_SELECT_W1": (_CANDIDATES[1], "w4_bounded_adjudicator", "AGG_NONE_SELECT_PARENT", ("w1",)),
    "A02_SELECT_W2": (_CANDIDATES[1], "w4_bounded_adjudicator", "AGG_NONE_SELECT_PARENT", ("w2",)),
    "A02_SELECT_W3": (_CANDIDATES[1], "w4_bounded_adjudicator", "AGG_NONE_SELECT_PARENT", ("w3",)),
    "A02_MEDIAN_VALID_WORKERS": (
        _CANDIDATES[1], "w4_bounded_adjudicator", "AGG_COMPONENTWISE_MEDIAN_VALID_WORKERS", ("VALID_W1_W2_W3",)
    ),
    "A02_MEDIAN_VALID_WORKERS_N0": (
        _CANDIDATES[1], "w4_bounded_adjudicator", "AGG_COMPONENTWISE_MEDIAN_VALID_WORKERS_N0", ("VALID_W1_W2_W3", "N0")
    ),
    "A02_DELIBERATE_FALLBACK": (_CANDIDATES[1], "w4_bounded_adjudicator", "AGG_COMMON_FALLBACK", ("N0",)),
    "A03_SELECT_TREND_ACTION": (
        _CANDIDATES[2], "w4_typed_arbiter", "AGG_NONE_SELECT_PARENT", ("w2.action_proposal",)
    ),
    "A03_SELECT_UNCERTAINTY_ACTION": (
        _CANDIDATES[2], "w4_typed_arbiter", "AGG_NONE_SELECT_PARENT", ("w3.action_proposal",)
    ),
    "A03_MEDIAN_SPECIALIST_BUNDLES_N0": (
        _CANDIDATES[2], "w4_typed_arbiter", "AGG_COMPONENTWISE_MEDIAN_SPECIALIST_BUNDLES_N0",
        ("w2.action_proposal", "w3.action_proposal", "N0")
    ),
    "A03_DELIBERATE_FALLBACK": (_CANDIDATES[2], "w4_typed_arbiter", "AGG_COMMON_FALLBACK", ("N0",)),
}

_PROMPT_SLOTS = ("w1", "w2", "w3", "w4")
_SCHEMA_NAMES = (
    "ForecastProposal.v1",
    "DiagnosticEvidence.v1",
    "ActionProposal.v1",
    "A03SpecialistOutput.v1",
    "Critique.v1",
    "RoutePlan.v1",
    "FinalDecision.v1",
    "FinalOutput.v1",
    "WorkerFailure.v1",
    "SlotClosure.v1",
    "LateResponseEvent.v1",
)

_IDENTITY_KEYS = frozenset(
    {
        "generation_id",
        "outer_fold_id",
        "origin_id_hash",
        "request_hash",
        "data_hash",
        "schema_hash",
    }
)

_TERMINAL_ATTEMPTS = {
    "FINISHED_VALID": 1,
    "FINISHED_SCHEMA_INVALID": 1,
    "PROVIDER_ERROR": 1,
    "TRANSPORT_FAILURE_CONSUMED": 1,
    "TIMEOUT_CONSUMED": 1,
    "NOT_STARTED_DEADLINE": 0,
}

_FAILURE_CODES_BY_STATE = {
    "FINISHED_SCHEMA_INVALID": frozenset(
        {
            "SCHEMA_INVALID",
            "PARENT_HASH_MISMATCH",
            "DATA_HASH_MISMATCH",
            "IDENTITY_MISMATCH",
        }
    ),
    "PROVIDER_ERROR": frozenset({"PROVIDER_ERROR"}),
    "TRANSPORT_FAILURE_CONSUMED": frozenset({"TRANSPORT_FAILURE_CONSUMED"}),
    "TIMEOUT_CONSUMED": frozenset({"TIMEOUT_CONSUMED"}),
    "NOT_STARTED_DEADLINE": frozenset({"NOT_STARTED_DEADLINE"}),
}


@dataclass(frozen=True, slots=True)
class ArchitectureCellContext:
    """Exact sealed identity and planned-key authority for one architecture cell."""

    identity: Mapping[str, Any]
    candidate_id: str
    planned_key_manifest: Mapping[str, Any]

    def __post_init__(self) -> None:
        frozen_identity = deepcopy(dict(self.identity))
        frozen_manifest = deepcopy(dict(self.planned_key_manifest))
        if set(frozen_identity) != _IDENTITY_KEYS:
            _fail("architecture cell identity keys differ")
        for name in ("generation_id", "outer_fold_id"):
            if not isinstance(frozen_identity[name], str) or not frozen_identity[name]:
                _fail(f"architecture cell identity {name} is invalid")
        for name in ("origin_id_hash", "request_hash", "data_hash", "schema_hash"):
            _require_sha256_value(frozen_identity[name], name)
        if self.candidate_id not in _CANDIDATES:
            _fail("architecture cell candidate is unknown")
        _validate_planned_key_manifest(frozen_manifest)
        object.__setattr__(self, "identity", frozen_identity)
        object.__setattr__(self, "planned_key_manifest", frozen_manifest)

    @property
    def planned_key_manifest_hash(self) -> str:
        return canonical_sha256(self.planned_key_manifest)


@dataclass(frozen=True, slots=True)
class ValidatedWorkflow:
    """One revalidated four-closure ledger and its sole effective parent set."""

    records: tuple[tuple[dict[str, Any], dict[str, Any]], ...]
    local_route_default: dict[str, Any] | None
    parents: Mapping[str, Mapping[str, Any]]
    w4_output: Mapping[str, Any]


def _fail(message: str) -> None:
    raise ArchitectureRegistryError(message)


def _require_sha256_value(value: Any, name: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{name} is not a lowercase SHA-256")


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (isinstance(value, int) or math.isfinite(value))
    )


def _validate_planned_key_manifest(manifest: Mapping[str, Any]) -> None:
    if set(manifest) != {"schema_version", "keys"}:
        _fail("planned-key manifest keys differ")
    if manifest.get("schema_version") != "PlannedKeyManifest.v1":
        _fail("planned-key manifest version differs")
    entries = manifest.get("keys")
    if not isinstance(entries, list) or not entries:
        _fail("planned-key manifest is empty")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {
            "key_id",
            "target_id",
            "unit",
            "minimum",
            "maximum",
        }:
            _fail("planned-key entry keys differ")
        for name in ("key_id", "target_id", "unit"):
            if not isinstance(entry[name], str) or not entry[name]:
                _fail(f"planned-key {name} is invalid")
        if entry["key_id"] in seen:
            _fail("planned-key manifest contains duplicate keys")
        seen.add(entry["key_id"])
        lower = entry["minimum"]
        upper = entry["maximum"]
        if lower is not None and not _is_finite_number(lower):
            _fail("planned-key minimum is invalid")
        if upper is not None and not _is_finite_number(upper):
            _fail("planned-key maximum is invalid")
        if lower is not None and upper is not None and lower > upper:
            _fail("planned-key domain is inverted")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_registry(path: str | Path = REGISTRY_PATH) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    value = strict_json_loads(raw)
    if not isinstance(value, dict):
        _fail("architecture registry must be a JSON object")
    return value


def _resolve_pointer(root: Mapping[str, Any], reference: str) -> Any:
    if not reference.startswith("#/"):
        _fail(f"non-local JSON Schema reference is forbidden: {reference}")
    value: Any = root
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, Mapping) or token not in value:
            _fail(f"unresolved JSON Schema reference: {reference}")
        value = value[token]
    return value


def _schema_equal(left: Any, right: Any) -> bool:
    try:
        return canonical_sha256(left) == canonical_sha256(right)
    except Exception:
        return False


def _validate_schema_node(
    root: Mapping[str, Any],
    schema: Mapping[str, Any],
    value: Any,
    *,
    path: str,
) -> None:
    """Validate the closed JSON-Schema subset used by the pinned registry."""

    if "$ref" in schema:
        target = _resolve_pointer(root, schema["$ref"])
        if not isinstance(target, Mapping):
            _fail(f"schema reference is not an object at {path}")
        _validate_schema_node(root, target, value, path=path)
        return

    if "const" in schema and not _schema_equal(value, schema["const"]):
        _fail(f"schema const mismatch at {path}")
    if "enum" in schema and not any(
        _schema_equal(value, item) for item in schema["enum"]
    ):
        _fail(f"schema enum mismatch at {path}")

    expected_type = schema.get("type")
    type_ok = {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": _is_finite_number(value),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if expected_type is not None and not type_ok.get(expected_type, False):
        _fail(f"schema type mismatch at {path}")

    if isinstance(value, Mapping):
        required = schema.get("required", [])
        if not isinstance(required, list) or any(key not in value for key in required):
            _fail(f"schema required property is absent at {path}")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            _fail(f"schema properties are invalid at {path}")
        if schema.get("additionalProperties") is False and not set(value) <= set(properties):
            _fail(f"schema additional property at {path}")
        for key, child in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                _validate_schema_node(
                    root,
                    child_schema,
                    child,
                    path=f"{path}/{key}",
                )

    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if minimum is not None and len(value) < minimum:
            _fail(f"schema minItems mismatch at {path}")
        if maximum is not None and len(value) > maximum:
            _fail(f"schema maxItems mismatch at {path}")
        if schema.get("uniqueItems") is True:
            hashes = [canonical_sha256(item) for item in value]
            if len(hashes) != len(set(hashes)):
                _fail(f"schema uniqueItems mismatch at {path}")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, child in enumerate(value):
                _validate_schema_node(
                    root,
                    item_schema,
                    child,
                    path=f"{path}/{index}",
                )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            _fail(f"schema minLength mismatch at {path}")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            _fail(f"schema pattern mismatch at {path}")

    if _is_finite_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            _fail(f"schema minimum mismatch at {path}")
        if "maximum" in schema and value > schema["maximum"]:
            _fail(f"schema maximum mismatch at {path}")

    for branch in schema.get("allOf", []):
        _validate_schema_node(root, branch, value, path=path)
    if "oneOf" in schema:
        matches = 0
        for branch in schema["oneOf"]:
            try:
                _validate_schema_node(root, branch, value, path=path)
            except ArchitectureRegistryError:
                continue
            matches += 1
        if matches != 1:
            _fail(f"schema oneOf matched {matches} branches at {path}")


def validate_artifact_instance(
    registry: Mapping[str, Any],
    schema_name: str,
    artifact: Mapping[str, Any],
) -> None:
    schemas = registry.get("artifact_schemas")
    if not isinstance(schemas, Mapping) or schema_name not in schemas:
        _fail(f"artifact schema is not registered: {schema_name}")
    if not isinstance(artifact, Mapping):
        _fail(f"{schema_name} artifact is not an object")
    _validate_schema_node(schemas, schemas[schema_name], artifact, path=schema_name)


def _walk(value: Any, path: str = "") -> Sequence[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, Mapping):
        for key, child in value.items():
            rows.extend(_walk(child, f"{path}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk(child, f"{path}/{index}"))
    return rows


def _schema_branches(schema: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for branch in schema.get("oneOf", []):
        props = branch.get("properties", {})
        route = props.get("route_id", {}).get("const")
        decision = props.get("decision_code", {}).get("const")
        key = route or decision
        if not isinstance(key, str) or key in result:
            _fail("schema discriminator branches are missing or duplicated")
        result[key] = props
    return result


def validate_registry(registry: Mapping[str, Any], *, verify_bound_files: bool = True) -> None:
    if registry.get("schema_version") != "cap-act.plan-a-architecture-registry.v1":
        _fail("architecture registry schema_version mismatch")
    if registry.get("status") != "PRESEAL_UNAPPROVED_NO_API":
        _fail("architecture registry is not the unapproved no-API artifact")
    if registry.get("candidate_count") != 3 or tuple(registry.get("candidates", {})) != _CANDIDATES:
        _fail("architecture registry must contain the exact three ordered candidates")
    authority = registry.get("authority", {})
    if authority.get("execution_authorized") is not False:
        _fail("architecture registry must not authorize execution")

    schemas = registry.get("artifact_schemas")
    if not isinstance(schemas, Mapping):
        _fail("artifact_schemas is absent")
    if schemas.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("artifact schema dialect mismatch")
    if schemas.get("$id") != "urn:plan-a:ArtifactSchemas.v1":
        _fail("artifact schema resource id mismatch")
    if not isinstance(schemas.get("$defs"), Mapping):
        _fail("artifact schema shared definitions are absent")
    expected_root_refs = {f"#/{name}" for name in _SCHEMA_NAMES}
    root_refs = {item.get("$ref") for item in schemas.get("oneOf", []) if isinstance(item, Mapping)}
    if root_refs != expected_root_refs:
        _fail("artifact schema resource does not expose the exact named schemas")
    for path, value in _walk(schemas, "artifact_schemas"):
        if isinstance(value, Mapping) and "$ref" in value:
            _resolve_pointer(schemas, value["$ref"])
        if path != "artifact_schemas" and isinstance(value, Mapping) and "$id" in value:
            _fail(f"nested schema resource changes reference scope at {path}")
        if isinstance(value, Mapping) and value.get("type") == "object":
            if value.get("additionalProperties") is not False:
                _fail(f"object schema is open at {path}")

    prompt_registry = registry.get("prompt_registry", {})
    for candidate_id in _CANDIDATES:
        prompts = prompt_registry.get(candidate_id, {})
        if tuple(prompts) != _PROMPT_SLOTS:
            _fail(f"prompt slots differ for {candidate_id}")
        for slot_id, prompt in prompts.items():
            raw = prompt.get("exact_prompt_bytes")
            if not isinstance(raw, str):
                _fail(f"prompt bytes are absent for {candidate_id}/{slot_id}")
            actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if actual != prompt.get("prompt_sha256"):
                _fail(f"prompt hash mismatch for {candidate_id}/{slot_id}")

    for candidate_id, candidate in registry["candidates"].items():
        slots = candidate.get("slots", [])
        if candidate.get("planned_physical_slots") != 4:
            _fail(f"planned slot count differs for {candidate_id}")
        if candidate.get("provider_send_attempts_range") != [0, 4]:
            _fail(f"provider attempt range differs for {candidate_id}")
        if tuple(item.get("slot_id") for item in slots) != _PROMPT_SLOTS:
            _fail(f"slot order differs for {candidate_id}")

    route_registry = registry.get("a03_route_registry", {})
    if set(route_registry) != set(_ROUTES):
        _fail("A03 route set differs")
    for route_id, (role, origin, assignments) in _ROUTES.items():
        record = route_registry[route_id]
        actual = tuple((item.get("specialist_role_id"), item.get("view_id")) for item in record.get("assignments", []))
        if actual != assignments:
            _fail(f"A03 route assignments differ for {route_id}")
        if record.get("router_selectable") is (route_id == "R00_DEFAULT_N0_GLOBAL"):
            _fail(f"A03 router_selectable differs for {route_id}")
        if record.get("local_default") is not (route_id == "R00_DEFAULT_N0_GLOBAL"):
            _fail(f"A03 local_default differs for {route_id}")
    route_branches = _schema_branches(schemas["RoutePlan.v1"])
    if set(route_branches) != set(_ROUTES):
        _fail("RoutePlan schema branches differ from route registry")
    for route_id, (role, origin, assignments) in _ROUTES.items():
        props = route_branches[route_id]
        expected = [
            {"specialist_role_id": item_role, "view_id": view}
            for item_role, view in assignments
        ]
        if props["role_id"].get("const") != role or props["route_origin"].get("const") != origin:
            _fail(f"RoutePlan role/origin mismatch for {route_id}")
        if props["assignments"].get("const") != expected:
            _fail(f"RoutePlan assignment branch mismatch for {route_id}")

    action_ids = set(registry.get("numerical_and_action_registry", {}).get("action_ids", []))
    views = registry.get("a03_assignment_views", {})
    for view_id, view in views.items():
        role = view.get("specialist_role_id")
        if (view_id.startswith("T_") and role != "w2_trend_specialist") or (
            view_id.startswith("U_") and role != "w3_uncertainty_specialist"
        ):
            _fail(f"A03 view role mismatch for {view_id}")
        if not set(view.get("allowed_action_ids", [])) <= action_ids:
            _fail(f"A03 view contains an unknown action for {view_id}")

    final_schema = schemas["FinalDecision.v1"]
    if "payload" in final_schema.get("properties", {}):
        _fail("provider FinalDecision must not contain a payload")
    decision_branches = _schema_branches(final_schema)
    if set(decision_branches) != set(_DECISIONS):
        _fail("FinalDecision branches differ from the closed decision registry")
    for decision_code, (candidate_id, role, aggregation, refs) in _DECISIONS.items():
        props = decision_branches[decision_code]
        if (
            props["candidate_id"].get("const") != candidate_id
            or props["role_id"].get("const") != role
            or props["aggregation_id"].get("const") != aggregation
            or props["source_refs"].get("const") != list(refs)
        ):
            _fail(f"FinalDecision mapping differs for {decision_code}")

    a03_slots = registry["candidates"][_CANDIDATES[2]]["slots"]
    if a03_slots[1].get("valid_output_schema") != "A03SpecialistOutput.v1" or a03_slots[2].get("valid_output_schema") != "A03SpecialistOutput.v1":
        _fail("A03 specialist slots do not close on one envelope")
    if a03_slots[3].get("parent_hash_visibility") != [
        "w1_route_plan_or_local_default_hash",
        "w2_specialist_output_envelope_hash",
        "w3_specialist_output_envelope_hash",
    ]:
        _fail("A03 w4 parent hashes are not exact envelopes")

    state_machine = registry.get("slot_failure_state_machine", {})
    if "LATE_DISCARDED" in state_machine.get("states", []):
        _fail("late response incorrectly replaces terminal closure")
    late_contract = registry.get("late_response_event_contract", {})
    late_schema = schemas["LateResponseEvent.v1"]
    if (
        late_contract.get("closure_mutation_allowed") is not False
        or late_contract.get("provider_send_delta") != 0
        or late_contract.get("prediction_overwrite_allowed") is not False
        or late_contract.get("event_state") != "LATE_RESPONSE_DISCARDED"
        or late_contract.get("precondition")
        != "SLOT_ALREADY_HAS_DURABLE_TIMEOUT_CONSUMED_CLOSURE_AND_PROVIDER_SEND_ATTEMPTS_EQUALS_1"
        or set(late_contract.get("required_fields", []))
        != set(late_schema.get("required", [])) - {"schema_version"}
    ):
        _fail("late response event may mutate closure")
    if len(schemas["WorkerFailure.v1"].get("allOf", [])) != 2:
        _fail("WorkerFailure schema lacks role/state discriminators")
    if len(schemas["SlotClosure.v1"].get("allOf", [])) != 2:
        _fail("SlotClosure schema lacks role/state discriminators")

    contract = registry.get("validator_contract")
    if verify_bound_files and contract is not None:
        root = Path(__file__).resolve().parents[2]
        validator_path = root / contract["validator_path"]
        test_path = root / contract["test_path"]
        if _sha256_file(validator_path) != contract.get("validator_sha256"):
            _fail("validator executable hash mismatch")
        if _sha256_file(test_path) != contract.get("test_sha256"):
            _fail("validator test hash mismatch")
        if canonical_sha256(schemas) != contract.get("artifact_schema_resource_sha256"):
            _fail("artifact schema resource hash mismatch")


def _slot_spec(
    registry: Mapping[str, Any], candidate_id: str, slot_id: str
) -> Mapping[str, Any]:
    candidate = registry.get("candidates", {}).get(candidate_id)
    if not isinstance(candidate, Mapping):
        _fail("candidate slot lookup has an unknown candidate")
    matches = [item for item in candidate.get("slots", []) if item.get("slot_id") == slot_id]
    if len(matches) != 1:
        _fail("candidate slot lookup is not unique")
    return matches[0]


def _validate_context_registry(
    registry: Mapping[str, Any], context: ArchitectureCellContext
) -> None:
    if context.candidate_id not in registry.get("candidates", {}):
        _fail("sealed cell candidate is absent from the registry")
    schema_hash = registry.get("validator_contract", {}).get(
        "artifact_schema_resource_sha256"
    )
    if (
        schema_hash != canonical_sha256(registry.get("artifact_schemas"))
        or context.identity.get("schema_hash") != schema_hash
    ):
        _fail("sealed cell schema hash differs from the pinned schema resource")


def _validate_artifact_context(
    artifact: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    role_id: str | None = None,
) -> None:
    if artifact.get("identity") != context.identity:
        _fail("artifact identity differs from sealed cell")
    if artifact.get("candidate_id") != context.candidate_id:
        _fail("artifact candidate differs from sealed cell")
    if role_id is not None and artifact.get("role_id") != role_id:
        _fail("artifact role differs from sealed slot")


def validate_route_plan(
    registry: Mapping[str, Any],
    route_plan: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    provider_output: bool,
    w1_failure: Mapping[str, Any] | None = None,
) -> None:
    _validate_context_registry(registry, context)
    if context.candidate_id != _CANDIDATES[2]:
        _fail("RoutePlan is valid only for the A03 candidate")
    validate_artifact_instance(registry, "RoutePlan.v1", route_plan)
    _validate_artifact_context(route_plan, context)
    route_id = route_plan.get("route_id")
    if route_id not in _ROUTES:
        _fail("RoutePlan route_id is not registered")
    role, origin, assignments = _ROUTES[route_id]
    actual = tuple((item.get("specialist_role_id"), item.get("view_id")) for item in route_plan.get("assignments", []))
    if route_plan.get("role_id") != role or route_plan.get("route_origin") != origin or actual != assignments:
        _fail("RoutePlan does not exactly match its registered branch")
    if provider_output and route_id == "R00_DEFAULT_N0_GLOBAL":
        _fail("provider router cannot select the local-default route")
    if not provider_output and route_id != "R00_DEFAULT_N0_GLOBAL":
        _fail("local route default must use R00")
    if provider_output:
        if w1_failure is not None or route_plan.get("parent_artifact_hashes") != []:
            _fail("provider route must not carry a local failure parent")
    else:
        if not isinstance(w1_failure, Mapping):
            _fail("local route default lacks its durable w1 failure trigger")
        validate_worker_failure(
            registry,
            w1_failure,
            context,
            slot_id="w1",
            parent_artifacts={},
        )
        if w1_failure.get("slot_closure_state") not in registry["candidates"][_CANDIDATES[2]]["router_failure_transition"]["trigger_states"]:
            _fail("local route default uses a non-triggering w1 state")
        if route_plan.get("parent_artifact_hashes") != [canonical_sha256(w1_failure)]:
            _fail("local route default is not bound to its durable w1 failure")


def validate_a03_specialist_output(
    registry: Mapping[str, Any],
    route_plan: Mapping[str, Any],
    envelope: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    w1_failure: Mapping[str, Any] | None = None,
) -> None:
    validate_route_plan(
        registry,
        route_plan,
        context,
        provider_output=route_plan.get("route_origin") == "PROVIDER_ROUTER",
        w1_failure=w1_failure,
    )
    validate_artifact_instance(registry, "A03SpecialistOutput.v1", envelope)
    _validate_artifact_context(envelope, context)
    role = envelope.get("role_id")
    assignment = {
        item["specialist_role_id"]: item["view_id"] for item in route_plan.get("assignments", [])
    }
    view_id = assignment.get(role)
    if view_id is None or envelope.get("assigned_view_id") != view_id:
        _fail("A03 specialist envelope uses the wrong assigned view")
    if envelope.get("parent_route_hash") != canonical_sha256(route_plan):
        _fail("A03 specialist parent route hash mismatch")
    diagnostic = envelope.get("diagnostic_evidence")
    action = envelope.get("action_proposal")
    validate_artifact_instance(registry, "DiagnosticEvidence.v1", diagnostic)
    validate_artifact_instance(registry, "ActionProposal.v1", action)
    _validate_artifact_context(diagnostic, context, role_id=role)
    _validate_artifact_context(action, context, role_id=role)
    if envelope.get("diagnostic_evidence_hash") != canonical_sha256(diagnostic):
        _fail("A03 diagnostic child hash mismatch")
    if envelope.get("action_proposal_hash") != canonical_sha256(action):
        _fail("A03 action child hash mismatch")
    if diagnostic.get("role_id") != role or action.get("role_id") != role:
        _fail("A03 specialist child role mismatch")
    if diagnostic.get("identity") != envelope.get("identity") or action.get("identity") != envelope.get("identity"):
        _fail("A03 specialist child identity mismatch")
    if diagnostic.get("candidate_id") != envelope.get("candidate_id") or action.get("candidate_id") != envelope.get("candidate_id"):
        _fail("A03 specialist child candidate mismatch")
    if action.get("diagnostic_evidence_hash") != envelope.get("diagnostic_evidence_hash"):
        _fail("A03 action does not bind its diagnostic child")
    if action.get("parent_route_hash") != envelope.get("parent_route_hash"):
        _fail("A03 action does not bind its route")
    if diagnostic.get("parent_artifact_hashes") != [canonical_sha256(route_plan)]:
        _fail("A03 diagnostic does not bind its route")
    allowed = set(registry["a03_assignment_views"][view_id]["allowed_action_ids"])
    if any(item.get("action_id") not in allowed for item in action.get("actions", [])):
        _fail("A03 specialist action is outside its assigned view")
    diagnostic_keys = [item.get("key_id") for item in diagnostic.get("evidence", [])]
    action_keys = [item.get("key_id") for item in action.get("actions", [])]
    if len(set(diagnostic_keys)) != len(diagnostic_keys) or diagnostic_keys != action_keys:
        _fail("A03 diagnostic/action keys are duplicate or misaligned")
    if action.get("planned_key_manifest_hash") != context.planned_key_manifest_hash:
        _fail("A03 action planned-key manifest differs from sealed cell")
    planned_keys = [item["key_id"] for item in context.planned_key_manifest["keys"]]
    if action_keys != planned_keys:
        _fail("A03 specialist output does not cover the sealed planned keys")


def validate_final_decision(
    registry: Mapping[str, Any],
    decision: Mapping[str, Any],
    context: ArchitectureCellContext,
    parents: Mapping[str, Mapping[str, Any]],
) -> None:
    _validate_context_registry(registry, context)
    validate_artifact_instance(registry, "FinalDecision.v1", decision)
    expected_role = _slot_spec(registry, context.candidate_id, "w4")["role_id"]
    _validate_artifact_context(decision, context, role_id=expected_role)
    code = decision.get("decision_code")
    if code not in _DECISIONS:
        _fail("FinalDecision decision_code is unknown")
    candidate_id, role, aggregation, refs = _DECISIONS[code]
    if (
        decision.get("candidate_id") != candidate_id
        or decision.get("role_id") != role
        or decision.get("aggregation_id") != aggregation
        or decision.get("source_refs") != list(refs)
    ):
        _fail("FinalDecision discriminator mapping mismatch")
    if set(parents) != {"w1", "w2", "w3"}:
        _fail("FinalDecision parents are not the exact three frozen slots")
    expected_hashes = [canonical_sha256(parents[slot]) for slot in ("w1", "w2", "w3")]
    if decision.get("parent_artifact_hashes") != expected_hashes:
        _fail("FinalDecision parent hashes differ from ordered closure outputs")


def validate_worker_failure(
    registry: Mapping[str, Any],
    failure: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    slot_id: str,
    parent_artifacts: Mapping[str, Mapping[str, Any]],
) -> None:
    _validate_context_registry(registry, context)
    validate_artifact_instance(registry, "WorkerFailure.v1", failure)
    slot = _slot_spec(registry, context.candidate_id, slot_id)
    _validate_artifact_context(failure, context, role_id=slot["role_id"])
    if failure.get("slot_id") != slot_id:
        _fail("worker failure slot differs from sealed slot")
    prompt_hash = registry["prompt_registry"][context.candidate_id][slot_id][
        "prompt_sha256"
    ]
    if failure.get("prompt_sha256") != prompt_hash:
        _fail("worker failure prompt hash differs from sealed prompt")
    expected_parent_slots = slot.get("parents", [])
    if set(parent_artifacts) != set(expected_parent_slots):
        _fail("worker failure parent set differs from sealed slot")
    expected_hashes = [canonical_sha256(parent_artifacts[item]) for item in expected_parent_slots]
    if failure.get("parent_artifact_hashes") != expected_hashes:
        _fail("worker failure parent hashes differ from ordered slot parents")
    state = failure.get("slot_closure_state")
    if failure.get("provider_send_attempts") != _TERMINAL_ATTEMPTS.get(state):
        _fail("worker failure attempt count contradicts terminal state")
    if failure.get("failure_code") not in _FAILURE_CODES_BY_STATE.get(state, frozenset()):
        _fail("worker failure code contradicts terminal state")


def _validate_parent_artifacts(
    registry: Mapping[str, Any],
    context: ArchitectureCellContext,
    parents: Mapping[str, Mapping[str, Any]],
    *,
    a03_w1_failure: Mapping[str, Any] | None = None,
) -> None:
    if set(parents) != {"w1", "w2", "w3"}:
        _fail("finalizer requires exactly w1, w2, and w3 parent artifacts")
    for slot_id in ("w1", "w2", "w3"):
        artifact = parents[slot_id]
        if not isinstance(artifact, Mapping):
            _fail("parent artifact is not an object")
        slot = _slot_spec(registry, context.candidate_id, slot_id)
        parent_inputs = {name: parents[name] for name in slot.get("parents", [])}
        schema_name = artifact.get("schema_version")
        if schema_name == "WorkerFailure.v1":
            validate_worker_failure(
                registry,
                artifact,
                context,
                slot_id=slot_id,
                parent_artifacts=parent_inputs,
            )
            continue
        if schema_name != slot.get("valid_output_schema"):
            _fail("parent artifact schema differs from sealed slot")
        if schema_name == "RoutePlan.v1":
            validate_route_plan(
                registry,
                artifact,
                context,
                provider_output=artifact.get("route_origin") == "PROVIDER_ROUTER",
                w1_failure=a03_w1_failure,
            )
        elif schema_name == "A03SpecialistOutput.v1":
            validate_a03_specialist_output(
                registry,
                parents["w1"],
                artifact,
                context,
                w1_failure=a03_w1_failure,
            )
        else:
            validate_artifact_instance(registry, schema_name, artifact)
            _validate_artifact_context(artifact, context, role_id=slot["role_id"])
            if schema_name == "ForecastProposal.v1":
                _proposal_bundle(
                    registry,
                    artifact,
                    context,
                    role_id=slot["role_id"],
                )
            expected_hashes = [canonical_sha256(parent_inputs[name]) for name in slot.get("parents", [])]
            if artifact.get("parent_artifact_hashes") != expected_hashes:
                _fail("parent artifact hashes differ from ordered slot parents")
            if schema_name == "Critique.v1" and [
                item.get("proposal_hash") for item in artifact.get("assessments", [])
            ] != expected_hashes:
                _fail("Critique assessments differ from ordered proposal parents")


def validate_slot_closure(
    registry: Mapping[str, Any],
    closure: Mapping[str, Any],
    output_artifact: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    parent_artifacts: Mapping[str, Mapping[str, Any]],
    a03_w1_failure: Mapping[str, Any] | None = None,
) -> None:
    validate_artifact_instance(registry, "SlotClosure.v1", closure)
    slot_id = closure.get("slot_id")
    if slot_id not in _PROMPT_SLOTS:
        _fail("slot closure has an unknown slot")
    slot = _slot_spec(registry, context.candidate_id, slot_id)
    _validate_artifact_context(closure, context, role_id=slot["role_id"])
    if closure.get("output_artifact_hash") != canonical_sha256(output_artifact):
        _fail("slot closure output hash differs from durable artifact")
    schema_name = output_artifact.get("schema_version")
    if closure.get("output_artifact_schema") != schema_name:
        _fail("slot closure output schema differs from durable artifact")
    state = closure.get("slot_closure_state")
    if closure.get("provider_send_attempts") != _TERMINAL_ATTEMPTS.get(state):
        _fail("slot closure attempt count contradicts terminal state")
    if state == "FINISHED_VALID":
        if schema_name != slot.get("valid_output_schema"):
            _fail("valid slot closure contains the wrong role artifact")
        if schema_name == "FinalDecision.v1":
            validate_final_decision(registry, output_artifact, context, parent_artifacts)
        elif schema_name == "RoutePlan.v1":
            validate_route_plan(
                registry,
                output_artifact,
                context,
                provider_output=True,
                w1_failure=None,
            )
        elif schema_name == "A03SpecialistOutput.v1":
            route = parent_artifacts.get("w1")
            if not isinstance(route, Mapping):
                _fail("A03 specialist closure lacks its route parent")
            validate_a03_specialist_output(
                registry,
                route,
                output_artifact,
                context,
                w1_failure=a03_w1_failure,
            )
        else:
            validate_artifact_instance(registry, schema_name, output_artifact)
            _validate_artifact_context(
                output_artifact,
                context,
                role_id=slot["role_id"],
            )
            if schema_name == "ForecastProposal.v1":
                _proposal_bundle(
                    registry,
                    output_artifact,
                    context,
                    role_id=slot["role_id"],
                )
            expected_parent_slots = slot.get("parents", [])
            expected_hashes = [
                canonical_sha256(parent_artifacts[name])
                for name in expected_parent_slots
            ]
            if output_artifact.get("parent_artifact_hashes") != expected_hashes:
                _fail("valid artifact hashes differ from ordered durable parents")
            if schema_name == "Critique.v1" and [
                item.get("proposal_hash")
                for item in output_artifact.get("assessments", [])
            ] != expected_hashes:
                _fail("Critique assessments differ from ordered durable parents")
    else:
        if schema_name != "WorkerFailure.v1":
            _fail("failed slot closure does not contain WorkerFailure.v1")
        validate_worker_failure(
            registry,
            output_artifact,
            context,
            slot_id=slot_id,
            parent_artifacts=parent_artifacts,
        )


def validate_workflow_closures(
    registry: Mapping[str, Any],
    context: ArchitectureCellContext,
    records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    *,
    local_route_default: Mapping[str, Any] | None = None,
) -> ValidatedWorkflow:
    """Validate one cell and derive every parent only from its durable ledger.

    Caller-supplied per-record parents are deliberately not accepted.  A03's
    local R00 route is a derived artifact and must hash-bind the exact durable
    w1 WorkerFailure in this same four-closure ledger.
    """

    if len(records) != 4:
        _fail("workflow must contain exactly four terminal closure records")
    if any(not isinstance(item, tuple) or len(item) != 2 for item in records):
        _fail("workflow records must contain only closure and durable output")
    slots = [item[0].get("slot_id") for item in records]
    if len(set(slots)) != 4 or set(slots) != set(_PROMPT_SLOTS):
        _fail("workflow closures are duplicated or incomplete")
    by_slot = {closure.get("slot_id"): (closure, output) for closure, output in records}
    outputs = {slot: by_slot[slot][1] for slot in _PROMPT_SLOTS}

    effective_w1 = outputs["w1"]
    if context.candidate_id == _CANDIDATES[2]:
        if effective_w1.get("schema_version") == "WorkerFailure.v1":
            if local_route_default is None:
                _fail("A03 w1 failure lacks its derived local route default")
            validate_route_plan(
                registry,
                local_route_default,
                context,
                provider_output=False,
                w1_failure=effective_w1,
            )
            effective_w1 = local_route_default
        elif local_route_default is not None:
            _fail("A03 provider route cannot coexist with a local route default")
    elif local_route_default is not None:
        _fail("local route default is valid only for A03")

    derived_parents: dict[str, dict[str, Mapping[str, Any]]] = {}
    for slot_id in _PROMPT_SLOTS:
        parent_slots = _slot_spec(registry, context.candidate_id, slot_id).get("parents", [])
        derived_parents[slot_id] = {
            name: (effective_w1 if name == "w1" else outputs[name])
            for name in parent_slots
        }
    for slot_id in _PROMPT_SLOTS:
        closure, output = by_slot[slot_id]
        validate_slot_closure(
            registry,
            closure,
            output,
            context,
            parent_artifacts=derived_parents[slot_id],
            a03_w1_failure=(
                outputs["w1"]
                if context.candidate_id == _CANDIDATES[2]
                and outputs["w1"].get("schema_version") == "WorkerFailure.v1"
                else None
            ),
        )
    parents = {
        "w1": effective_w1,
        "w2": outputs["w2"],
        "w3": outputs["w3"],
    }
    frozen_records = tuple(
        (deepcopy(dict(by_slot[slot][0])), deepcopy(dict(by_slot[slot][1])))
        for slot in _PROMPT_SLOTS
    )
    return ValidatedWorkflow(
        records=frozen_records,
        local_route_default=(
            None if local_route_default is None else deepcopy(dict(local_route_default))
        ),
        parents=deepcopy(parents),
        w4_output=deepcopy(dict(outputs["w4"])),
    )


def append_late_response_event(
    registry: Mapping[str, Any],
    closure: Mapping[str, Any],
    output_artifact: Mapping[str, Any],
    event: Mapping[str, Any],
    existing_events: Sequence[Mapping[str, Any]],
    context: ArchitectureCellContext,
    *,
    parent_artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Append a late event without granting closure or prediction authority."""

    validate_slot_closure(
        registry,
        closure,
        output_artifact,
        context,
        parent_artifacts=parent_artifacts,
    )
    validate_artifact_instance(registry, "LateResponseEvent.v1", event)
    if event.get("identity") != context.identity:
        _fail("late event identity differs from sealed cell")
    if event.get("candidate_id") != context.candidate_id:
        _fail("late event candidate differs from sealed cell")
    if event.get("slot_id") != closure.get("slot_id"):
        _fail("late event slot differs from terminal closure")
    if (
        closure.get("provider_send_attempts") != 1
        or closure.get("slot_closure_state") != "TIMEOUT_CONSUMED"
    ):
        _fail("late event requires a sent slot already closed as timeout")
    closure_hash = canonical_sha256(closure)
    if event.get("original_terminal_closure_hash") != closure_hash:
        _fail("late event does not bind the original terminal closure")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_responses: set[tuple[str, str]] = set()
    previous_monotonic_ns: int | None = None
    for existing in existing_events:
        validate_artifact_instance(registry, "LateResponseEvent.v1", existing)
        if (
            existing.get("identity") != context.identity
            or existing.get("candidate_id") != context.candidate_id
            or existing.get("slot_id") != closure.get("slot_id")
            or existing.get("original_terminal_closure_hash") != closure_hash
        ):
            _fail("existing late event belongs to another immutable closure")
        event_hash = canonical_sha256(existing)
        if event_hash in seen:
            _fail("duplicate late event")
        response_key = (
            existing.get("original_terminal_closure_hash"),
            existing.get("late_response_sha256"),
        )
        if response_key in seen_responses:
            _fail("duplicate late response observation")
        observed = existing.get("observed_at_monotonic_ns")
        if previous_monotonic_ns is not None and observed <= previous_monotonic_ns:
            _fail("existing late events are not in strict append order")
        previous_monotonic_ns = observed
        seen.add(event_hash)
        seen_responses.add(response_key)
        result.append(deepcopy(dict(existing)))
    new_hash = canonical_sha256(event)
    if new_hash in seen:
        _fail("duplicate late event")
    new_response_key = (
        event.get("original_terminal_closure_hash"),
        event.get("late_response_sha256"),
    )
    if new_response_key in seen_responses:
        _fail("duplicate late response observation")
    if result and event.get("observed_at_monotonic_ns") <= result[-1].get(
        "observed_at_monotonic_ns"
    ):
        _fail("late events are not in strict monotonic append order")
    result.append(deepcopy(dict(event)))
    return tuple(result)


def _proposal_bundle(
    registry: Mapping[str, Any],
    proposal: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    role_id: str,
) -> dict[str, Any] | None:
    if proposal.get("schema_version") != "ForecastProposal.v1":
        return None
    validate_artifact_instance(registry, "ForecastProposal.v1", proposal)
    _validate_artifact_context(proposal, context, role_id=role_id)
    if proposal.get("planned_key_manifest_hash") != context.planned_key_manifest_hash:
        _fail("forecast proposal planned-key manifest differs from sealed cell")
    bundle = {
        "payload_type": "DIRECT_BUNDLE",
        "planned_key_manifest_hash": proposal["planned_key_manifest_hash"],
        "forecasts": deepcopy(proposal["forecasts"]),
    }
    _validate_direct_bundle(registry, bundle, context)
    return bundle


def _validate_direct_bundle(
    registry: Mapping[str, Any],
    bundle: Mapping[str, Any],
    context: ArchitectureCellContext,
) -> None:
    _validate_context_registry(registry, context)
    schemas = registry["artifact_schemas"]
    _validate_schema_node(
        schemas,
        schemas["$defs"]["direct_bundle"],
        bundle,
        path="direct_bundle",
    )
    if bundle.get("planned_key_manifest_hash") != context.planned_key_manifest_hash:
        _fail("direct bundle planned-key manifest differs from sealed cell")
    domains = {
        item["key_id"]: item for item in context.planned_key_manifest["keys"]
    }
    keys: set[str] = set()
    for entry in bundle["forecasts"]:
        key = entry.get("key_id")
        q = entry.get("quantiles", {})
        values = [q.get("q10"), q.get("q25"), entry.get("point"), q.get("q75"), q.get("q90")]
        if not isinstance(key, str) or key in keys or key not in domains:
            _fail("direct bundle keys are absent or duplicated")
        if any(not _is_finite_number(value) for value in values):
            _fail("direct bundle contains a nonnumeric forecast")
        if values != sorted(values):
            _fail("direct bundle quantiles/point are not nested")
        lower = domains[key]["minimum"]
        upper = domains[key]["maximum"]
        if lower is not None and any(value < lower for value in values):
            _fail("direct bundle value is below the sealed target/unit domain")
        if upper is not None and any(value > upper for value in values):
            _fail("direct bundle value is above the sealed target/unit domain")
        keys.add(key)
    if [item["key_id"] for item in bundle["forecasts"]] != list(domains):
        _fail("direct bundle does not exactly cover the sealed planned keys")


def _median_bundles(
    registry: Mapping[str, Any],
    bundles: Sequence[Mapping[str, Any]],
    context: ArchitectureCellContext,
) -> dict[str, Any]:
    if not bundles:
        _fail("componentwise median has no input bundles")
    for bundle in bundles:
        _validate_direct_bundle(registry, bundle, context)
    manifest = bundles[0]["planned_key_manifest_hash"]
    maps = [{item["key_id"]: item for item in bundle["forecasts"]} for bundle in bundles]
    if any(bundle["planned_key_manifest_hash"] != manifest or set(item) != set(maps[0]) for bundle, item in zip(bundles, maps)):
        _fail("componentwise median inputs do not share planned keys")
    confidence_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    reverse_confidence = {value: key for key, value in confidence_order.items()}
    forecasts: list[dict[str, Any]] = []
    for key in (
        item["key_id"] for item in context.planned_key_manifest["keys"]
    ):
        entries = [item[key] for item in maps]
        forecasts.append(
            {
                "key_id": key,
                "point": median(entry["point"] for entry in entries),
                "quantiles": {
                    name: median(entry["quantiles"][name] for entry in entries)
                    for name in ("q10", "q25", "q75", "q90")
                },
                "confidence_bin": reverse_confidence[
                    min(confidence_order[entry["confidence_bin"]] for entry in entries)
                ],
            }
        )
    output = {"payload_type": "DIRECT_BUNDLE", "planned_key_manifest_hash": manifest, "forecasts": forecasts}
    _validate_direct_bundle(registry, output, context)
    return output


def _execute_actions(
    registry: Mapping[str, Any],
    action_proposal: Mapping[str, Any],
    context: ArchitectureCellContext,
    *,
    n0: Mapping[str, Any],
    numerical_bundles: Mapping[str, Mapping[str, Any]],
    scale_train: Mapping[str, float],
) -> dict[str, Any]:
    validate_artifact_instance(registry, "ActionProposal.v1", action_proposal)
    _validate_artifact_context(action_proposal, context)
    _validate_direct_bundle(registry, n0, context)
    if action_proposal.get("planned_key_manifest_hash") != n0.get("planned_key_manifest_hash"):
        _fail("action proposal planned-key manifest differs from N0")
    base_by_key = {item["key_id"]: item for item in n0["forecasts"]}
    action_semantics = registry["numerical_and_action_registry"]["action_semantics"]
    output: list[dict[str, Any]] = []
    for action in action_proposal.get("actions", []):
        key = action["key_id"]
        action_id = action["action_id"]
        if key not in base_by_key:
            _fail("action key is absent from N0")
        if action_id == "FALLBACK":
            entry = deepcopy(base_by_key[key])
        elif action_id.startswith("EMIT_"):
            model_id = action_id.removeprefix("EMIT_")
            source = numerical_bundles.get(model_id)
            if source is None:
                _fail(f"numerical bundle is absent for {model_id}")
            _validate_direct_bundle(registry, source, context)
            if source.get("planned_key_manifest_hash") != n0.get("planned_key_manifest_hash"):
                _fail(f"numerical bundle planned-key manifest differs for {model_id}")
            source_map = {item["key_id"]: item for item in source["forecasts"]}
            if key not in source_map:
                _fail(f"numerical bundle lacks action key for {model_id}")
            entry = deepcopy(source_map[key])
        elif action_id.startswith("FUSE_"):
            fusion_id = action_id.removeprefix("FUSE_")
            source = numerical_bundles.get(fusion_id)
            if source is None:
                _fail(f"numerical bundle is absent for {fusion_id}")
            _validate_direct_bundle(registry, source, context)
            if source.get("planned_key_manifest_hash") != n0.get("planned_key_manifest_hash"):
                _fail(f"numerical bundle planned-key manifest differs for {fusion_id}")
            source_map = {item["key_id"]: item for item in source["forecasts"]}
            if key not in source_map:
                _fail(f"numerical bundle lacks action key for {fusion_id}")
            entry = deepcopy(source_map[key])
        elif action_id.startswith("SHIFT_"):
            entry = deepcopy(base_by_key[key])
            scale = scale_train.get(key)
            if not _is_finite_number(scale) or scale < 0:
                _fail("SHIFT action lacks a nonnegative training-only scale")
            delta = action_semantics[action_id]["scale_multiplier"] * scale
            entry["point"] += delta
            for name in ("q10", "q25", "q75", "q90"):
                entry["quantiles"][name] += delta
        elif action_id.startswith("INFLATE_"):
            entry = deepcopy(base_by_key[key])
            factor = action_semantics[action_id]["interval_width_multiplier"]
            point = entry["point"]
            for name in ("q10", "q25", "q75", "q90"):
                entry["quantiles"][name] = point + factor * (entry["quantiles"][name] - point)
        else:
            _fail(f"unknown action id: {action_id}")
        output.append(entry)
    bundle = {
        "payload_type": "DIRECT_BUNDLE",
        "planned_key_manifest_hash": action_proposal["planned_key_manifest_hash"],
        "forecasts": output,
    }
    _validate_direct_bundle(registry, bundle, context)
    if {item["key_id"] for item in output} != set(base_by_key):
        _fail("action proposal does not cover every planned N0 key")
    return bundle


def _execute_valid_decision(
    registry: Mapping[str, Any],
    context: ArchitectureCellContext,
    decision: Mapping[str, Any],
    parents: Mapping[str, Mapping[str, Any]],
    *,
    n0: Mapping[str, Any],
    numerical_bundles: Mapping[str, Mapping[str, Any]],
    scale_train: Mapping[str, float],
) -> tuple[str, dict[str, Any], list[str]]:
    code = decision["decision_code"]
    if code.endswith("DELIBERATE_FALLBACK"):
        return (
            "DELIBERATE_FALLBACK",
            {"payload_type": "COMMON_FALLBACK", "fallback_id": "N0=b_star=FALLBACK"},
            [canonical_sha256(n0)],
        )
    if code.startswith("A01_SELECT_") or code.startswith("A02_SELECT_"):
        slot_id = code.rsplit("_", 1)[-1].lower()
        proposal = parents[slot_id]
        role_id = _slot_spec(registry, context.candidate_id, slot_id)["role_id"]
        bundle = _proposal_bundle(
            registry,
            proposal,
            context,
            role_id=role_id,
        )
        if bundle is None:
            _fail("selected forecast parent is not valid")
        return "ACTIVE", bundle, [canonical_sha256(proposal)]
    if code == "A01_MEDIAN_W1_W2_N0":
        bundles: list[Mapping[str, Any]] = []
        source_hashes: list[str] = []
        for slot_id in ("w1", "w2"):
            proposal = parents[slot_id]
            bundle = _proposal_bundle(
                registry,
                proposal,
                context,
                role_id=_slot_spec(registry, context.candidate_id, slot_id)["role_id"],
            )
            if bundle is None:
                _fail("A01 median requires two valid forecast parents")
            bundles.append(bundle)
            source_hashes.append(canonical_sha256(proposal))
        bundles.append(n0)
        source_hashes.append(canonical_sha256(n0))
        return "ACTIVE", _median_bundles(registry, bundles, context), source_hashes
    if code in {"A02_MEDIAN_VALID_WORKERS", "A02_MEDIAN_VALID_WORKERS_N0"}:
        valid: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
        for slot_id in ("w1", "w2", "w3"):
            proposal = parents[slot_id]
            bundle = _proposal_bundle(
                registry,
                proposal,
                context,
                role_id=_slot_spec(registry, context.candidate_id, slot_id)["role_id"],
            )
            if bundle is not None:
                valid.append((slot_id, proposal, bundle))
        minimum = 1 if code.endswith("_N0") else 2
        if len(valid) < minimum:
            _fail("A02 valid-worker median does not meet its frozen minimum")
        bundles = [item[2] for item in valid]
        source_hashes = [canonical_sha256(item[1]) for item in valid]
        if code.endswith("_N0"):
            bundles.append(n0)
            source_hashes.append(canonical_sha256(n0))
        return "ACTIVE", _median_bundles(registry, bundles, context), source_hashes
    if code.startswith("A03_"):
        specialist_bundles: list[dict[str, Any]] = []
        specialist_hashes: list[str] = []
        selected_slots = (
            ("w2",)
            if code == "A03_SELECT_TREND_ACTION"
            else ("w3",)
            if code == "A03_SELECT_UNCERTAINTY_ACTION"
            else ("w2", "w3")
        )
        for slot_id in selected_slots:
            envelope = parents[slot_id]
            if envelope.get("schema_version") != "A03SpecialistOutput.v1":
                _fail("A03 decision selected a missing specialist envelope")
            specialist_bundles.append(
                _execute_actions(
                    registry,
                    envelope["action_proposal"],
                    context,
                    n0=n0,
                    numerical_bundles=numerical_bundles,
                    scale_train=scale_train,
                )
            )
            specialist_hashes.append(canonical_sha256(envelope))
        if code == "A03_MEDIAN_SPECIALIST_BUNDLES_N0":
            payload = _median_bundles(
                registry,
                [*specialist_bundles, n0],
                context,
            )
            specialist_hashes.append(canonical_sha256(n0))
        else:
            payload = specialist_bundles[0]
        return "ACTIVE", payload, specialist_hashes
    _fail("no local executor branch for decision")


def _validate_final_output(
    registry: Mapping[str, Any],
    output: Mapping[str, Any],
    context: ArchitectureCellContext,
) -> None:
    validate_artifact_instance(registry, "FinalOutput.v1", output)
    if output.get("identity") != context.identity:
        _fail("FinalOutput identity differs from sealed cell")
    if output.get("candidate_id") != context.candidate_id:
        _fail("FinalOutput candidate differs from sealed cell")
    if output.get("local_executor_sha256") != _sha256_file(Path(__file__)):
        _fail("FinalOutput local executor hash differs from executable bytes")
    if output.get("planned_key_manifest_hash") != context.planned_key_manifest_hash:
        _fail("FinalOutput planned-key manifest differs from sealed cell")
    if output.get("execution_status") == "ACTIVE":
        _validate_direct_bundle(registry, output["payload"], context)


def _error_fallback_output(
    context: ArchitectureCellContext,
    *,
    trigger_type: str,
    trigger_hash: str,
    n0: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "FinalOutput.v1",
        "identity": deepcopy(dict(context.identity)),
        "candidate_id": context.candidate_id,
        "local_executor_sha256": _sha256_file(Path(__file__)),
        "finalization_trigger_type": trigger_type,
        "finalization_trigger_hash": trigger_hash,
        "source_artifact_hashes": [canonical_sha256(n0)],
        "planned_key_manifest_hash": context.planned_key_manifest_hash,
        "execution_status": "ERROR_FALLBACK",
        "payload": {
            "payload_type": "COMMON_FALLBACK",
            "fallback_id": "N0=b_star=FALLBACK",
        },
    }


def execute_final_decision(
    registry: Mapping[str, Any],
    context: ArchitectureCellContext,
    records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    *,
    n0: Mapping[str, Any],
    local_route_default: Mapping[str, Any] | None = None,
    numerical_bundles: Mapping[str, Mapping[str, Any]] | None = None,
    scale_train: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Finalize one cell solely from its revalidated durable workflow ledger.

    Frozen registry/context/N0/closure-ledger defects are formal invariant
    errors and raise. A typed w4 failure or an operationally unusable valid
    decision commits the exact common ERROR_FALLBACK.
    """

    validate_registry(registry, verify_bound_files=False)
    _validate_direct_bundle(registry, n0, context)
    workflow = validate_workflow_closures(
        registry,
        context,
        records,
        local_route_default=local_route_default,
    )
    parents = workflow.parents
    durable_w1 = workflow.records[0][1]
    _validate_parent_artifacts(
        registry,
        context,
        parents,
        a03_w1_failure=(
            durable_w1
            if context.candidate_id == _CANDIDATES[2]
            and durable_w1.get("schema_version") == "WorkerFailure.v1"
            else None
        ),
    )
    w4_output = workflow.w4_output
    if w4_output.get("schema_version") == "WorkerFailure.v1":
        output = _error_fallback_output(
            context,
            trigger_type="W4_WORKER_FAILURE",
            trigger_hash=canonical_sha256(w4_output),
            n0=n0,
        )
        _validate_final_output(registry, output, context)
        return output

    decision = w4_output
    validate_final_decision(registry, decision, context, parents)

    try:
        status, payload, source_hashes = _execute_valid_decision(
            registry,
            context,
            decision,
            parents,
            n0=n0,
            numerical_bundles=numerical_bundles or {},
            scale_train=scale_train or {},
        )
    except ArchitectureRegistryError:
        output = _error_fallback_output(
            context,
            trigger_type="INVALID_FINAL_DECISION",
            trigger_hash=canonical_sha256(decision),
            n0=n0,
        )
        _validate_final_output(registry, output, context)
        return output

    output = {
        "schema_version": "FinalOutput.v1",
        "identity": deepcopy(dict(context.identity)),
        "candidate_id": context.candidate_id,
        "local_executor_sha256": _sha256_file(Path(__file__)),
        "finalization_trigger_type": "VALID_FINAL_DECISION",
        "finalization_trigger_hash": canonical_sha256(decision),
        "source_artifact_hashes": source_hashes,
        "planned_key_manifest_hash": context.planned_key_manifest_hash,
        "execution_status": status,
        "payload": payload,
    }
    _validate_final_output(registry, output, context)
    return output
