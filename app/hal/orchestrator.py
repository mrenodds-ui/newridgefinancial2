from __future__ import annotations

import difflib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .accounting_tools import draft_journal_entry_for_common_case, get_chart_of_accounts, is_period_open
from .accounting_validation import build_journal_validation
from .audit import get_recent_hal_audits, record_hal_audit
from app.ai_local_config import (
    LocalAIConfigError,
    get_backend_base_url,
    get_backend_model_name,
    get_frontend_base_url,
    get_frontend_model_name,
    get_hal_fast_model_base_url,
    get_hal_fast_model_name,
    get_hal_fast_model_timeout_seconds,
    get_hal_main_model_timeout_seconds,
    get_model_routing_snapshot,
    hal_fast_model_enabled,
    load_local_model_profile_config,
    require_lane_runtime,
    resolve_lane_profile,
)
from app.evaluation.client import generate_response_result, get_ollama_runtime_status, load_json_file, run_structured_output_workflow
from app.services import build_softdent_snapshot, fetch_softdent_dashboard_aggregate, list_local_accounting_documents, load_softdent_ar_rows, load_softdent_claim_rows, run_ci_gates, run_rebuild_receipt, run_refresh_and_verify, run_smoke_tests
from .hardware_tools import build_monitor_mutation_intent, get_monitor_status

from .financial_tools import ReportPeriod, get_ar_aging_report, get_balance_sheet_report, get_controlled_patient_context, get_financial_source_status, get_live_financial_context, get_profit_loss_report, get_softdent_collection_delta_status, get_softdent_payer_mix_status, get_softdent_provider_ranking_status
from .index_builder import refresh_hal_index
from .posting_queue import DRAFT_STATUS_DRAFT_ONLY, DRAFT_STATUS_ENQUEUED, ENQUEUE_MODE_AUTO_VALIDATED_AI, ENQUEUE_MODE_MANUAL_REVIEW_QUEUE, POSTING_QUEUE_STATUS_PENDING_REVIEW, PostingQueueReviewAction
from .retrieval import retrieve_relevant_context
from .sanitization import sanitize_hal_text
from .safety import append_ai_activity_log, get_ai_activity_log_path, get_ai_review_plan_directory, get_ai_workspace_path, write_review_step_file
from .storage import get_accounting_posting_queue_entry, get_accounting_posting_queue_metrics, get_hal_autonomy_run, get_hal_conversation_state, get_hal_storage_path, get_recent_accounting_posting_queue_activity, get_recent_accounting_posting_queue_entries, get_recent_hal_autonomy_runs, insert_accounting_posting_queue_entry, save_hal_autonomy_run, save_hal_conversation_state, update_accounting_posting_queue_review
from .vector_store import count_hal_collection_documents, get_embedding_provider_name, get_hal_chroma_path
from uuid import uuid4


HAL_MODE = "local-rag-phase-1"
PRIMARY_PROFILE_ALIAS = "chat"
FAST_PROFILE_ALIAS = "chat_fast"
PRIMARY_NUM_PREDICT = 64
PRIMARY_CONTEXT_LIMIT = 2
PRIMARY_EXCERPT_CHAR_LIMIT = 300
PRIMARY_SUMMARY_CHAR_LIMIT = 600
FAST_NUM_PREDICT = 48
FAST_CONTEXT_LIMIT = 1
FAST_EXCERPT_CHAR_LIMIT = 200
ESCALATION_MARKER = "[NEEDS_ESCALATION]"
SECOND_OPINION_PROFILE_ALIAS = "chat_second_opinion"
SECOND_OPINION_CONTEXT_LIMIT = 2
SECOND_OPINION_EXCERPT_CHAR_LIMIT = 300
SECOND_OPINION_SUMMARY_CHAR_LIMIT = 1200
SECOND_OPINION_NUM_PREDICT = 64
LOCAL_MODEL_PROFILE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "evals" / "local_model_profiles.json"


def _hal_ask_model_routing_enabled() -> bool:
    return os.getenv("HAL_ASK_MODEL_ROUTING", "1").strip().lower() not in {"0", "false", "no", "off"}


def _hal_ask_fast_path_enabled() -> bool:
    """When enabled, HAL tries the deterministic answer first and skips the local LLM when it is substantive."""
    return os.getenv("HAL_ASK_FAST_PATH", "1").strip().lower() not in {"0", "false", "no", "off"}


_MINIMAL_OPERATING_PICTURE: dict[str, object] = {"summary": ""}
_LANE_RUNTIME_CACHE_SECONDS = float(os.getenv("HAL_LANE_RUNTIME_CACHE_SECONDS", "30"))
_lane_runtime_cache: dict[str, tuple[float, dict[str, object]]] = {}
_lane_runtime_cache_lock = threading.Lock()
_deterministic_status_cache: dict[str, tuple[float, dict[str, object]]] = {}
_deterministic_status_cache_lock = threading.Lock()


HAL_PHASES = [
    "Authenticate operator",
    "Sanitize question",
    "Retrieve approved context",
    "Compose financial-only answer",
    "Record audit metadata",
]
HAL_CAPABILITY_MATRIX = [
    {"capability_id": "financial_qa", "label": "General HAL financial Q&A", "lane": "general_hal"},
    {"capability_id": "softdent_live_snapshot", "label": "SoftDent live snapshot review", "lane": "deterministic"},
    {"capability_id": "softdent_provider_ranking", "label": "SoftDent provider ranking", "lane": "deterministic"},
    {"capability_id": "softdent_payer_mix", "label": "SoftDent payer mix review", "lane": "deterministic"},
    {"capability_id": "softdent_collection_delta", "label": "SoftDent collections delta review", "lane": "deterministic"},
    {"capability_id": "softdent_claims_lookup", "label": "SoftDent claims export review", "lane": "reviewed_read_only"},
    {"capability_id": "softdent_clinical_notes_lookup", "label": "SoftDent clinical-note export review", "lane": "reviewed_read_only"},
    {"capability_id": "insurance_narrative", "label": "Insurance narrative drafting", "lane": "reviewed_read_only"},
    {"capability_id": "patient_dossier", "label": "Patient dossier synthesis", "lane": "reviewed_read_only"},
    {"capability_id": "accounting_policy_answer", "label": "Accounting policy answer", "lane": "policy"},
    {"capability_id": "journal_draft", "label": "Journal draft preparation", "lane": "review_required"},
    {"capability_id": "posting_queue_review", "label": "QuickBooks posting queue review", "lane": "review_required"},
]
HAL_FILE_OWNERSHIP_AREAS = [
    "dashboard shell",
    "hal orchestrator",
    "local runtime routing",
    "retrieval and vector store",
    "audit and ledger",
    "softdent aggregates",
    "softdent patient exports",
    "quickbooks summaries",
    "accounting policy workflows",
    "developer and operator endpoints",
]
HAL_COMPLETION_LEDGER = [
    {
        "entry_id": "registered-shell-policy",
        "status": "passed",
        "summary": "Registered-command-only shell policy is exposed through /api/hal/shell/commands.",
    },
    {
        "entry_id": "unit-test-completion-ledger",
        "status": "passed",
        "summary": "Latest completed work passed the unit-test completion ledger check.",
    },
]
HAL_SHELL_VERIFICATION_ENDPOINT = "/api/hal/shell/commands"
HAL_SHELL_POLICY_PURPOSE = "Explain and preserve the registered-command-only shell policy for HAL operators."
HAL_AUTONOMY_PROFILE_ENDPOINT = "/api/hal9000/autonomy/profile"
HAL_AUTONOMY_RUNS_ENDPOINT = "/api/hal9000/autonomy/runs"
HAL_AUTONOMY_LOOP_MODE = "deterministic_think_act_observe"
HAL_AUTONOMY_SANDBOX_MODE = "local_backend_registry_only"
HAL_AUTONOMY_WORKING_DIRECTORY = "."
HAL_AUTONOMY_DEFAULT_MAX_STEPS = 3
HAL_AUTONOMY_MAX_STEPS = 12
HAL_SHELL_BLOCKED_ACTIONS = [
    "free-form shell",
    "destructive system actions",
    "QuickBooks write/apply commands",
    "print secrets",
]
HAL_SHELL_CONFIRMATION_REQUIRED_ACTIONS = [
    "add a new registered command",
    "run process-state command",
]
HAL_CAPABILITY_HIERARCHY = [
    {
        "tier": "tier_1",
        "priority": "high",
        "label": "Critical actions",
        "scope": "Data accuracy, security boundaries, permanent writes, destructive operations, and system-affecting mutations.",
        "execution_policy": "Never execute autonomously. Return a proposal or draft only and wait for explicit human confirmation before any write, delete, move, or apply step.",
        "escalation_rule": "Treat any request that could change ledgers, patient records, secrets, devices, or production state as confirmation-required.",
    },
    {
        "tier": "tier_2",
        "priority": "medium",
        "label": "Read and analyze",
        "scope": "Read-only extraction, OCR review, cross-referencing approved exports, and deterministic query-backed analysis.",
        "execution_policy": "Autonomous read-only analysis is allowed within approved sources and audited local tools.",
        "escalation_rule": "If HAL detects a mismatch, missing support, or conflicting totals, it must stop the workflow and raise [ALERT] with the discrepancy.",
    },
    {
        "tier": "tier_3",
        "priority": "low",
        "label": "Assist and explain",
        "scope": "Formula help, summaries, explanations, syntax help, and general how-to guidance.",
        "execution_policy": "Answer immediately with concise, low-overhead guidance when no protected write path or read-only discrepancy is involved.",
        "escalation_rule": "Prefer speed and brevity unless the request crosses into Tier 1 or Tier 2 behavior.",
    },
]
REPORT_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SAFE_PACKAGE_SCRIPT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9:_-]+$")
logger = logging.getLogger(__name__)
FOLLOW_UP_PHRASES = (
    "based on that",
    "we just covered",
    "just covered",
    "do not repeat",
    "without inventing anything new",
    "what should i do first",
    "what should i do next",
    "before lunch",
    "summarize the top two action items",
)

HAL_VOICE_PROFILES = {
    "primary": {
        "lane": "primary",
        "label": "Ask HAL",
        "tone": "direct and practical",
        "style_notes": [
            "Lead with the practical answer for the signed-in office user.",
            "Separate known facts, runtime status, and recommendations.",
            "Use patient names when useful for authorized internal workflows.",
        ],
    },
    "fast_office": {
        "lane": "fast_model",
        "label": "Ask HAL",
        "tone": "brief and practical",
        "style_notes": [
            "Routine office wording with verified facts only.",
            "Keep answers short and staff-ready.",
        ],
    },
    "deeper_review": {
        "lane": "fallback",
        "label": "HAL needed a deeper review",
        "tone": "grounded and staff-assistant",
        "style_notes": [
            "Internal deeper review completed after the frontline answer was inconclusive.",
            "Call out missing data and the next safe action.",
        ],
    },
    "second_opinion": {
        "lane": "second_opinion",
        "label": "HAL needed a deeper review",
        "tone": "grounded and staff-assistant",
        "style_notes": [
            "Answer like an internal teammate reviewing the case.",
            "Add one verification angle when useful.",
            "Call out tradeoffs, missing data, and the next safe action.",
        ],
    },
    "patient_workflow": {
        "lane": "patient_workflow",
        "label": "Patient workflow",
        "tone": "case-focused and actionable",
        "style_notes": [
            "Stay specific to the matched patient context.",
            "Use patient names naturally for authorized office workflows.",
            "Separate facts, recommendations, and review boundaries.",
        ],
    },
    "policy": {
        "lane": "policy",
        "label": "Policy guidance",
        "tone": "measured and review-oriented",
        "style_notes": [
            "Frame the answer as draft guidance for internal staff.",
            "Ground the answer in approved citations.",
            "Make the need for review explicit without sounding defensive.",
        ],
    },
}

GOVERNED_MEMORY_PROPOSAL_PHRASE = (
    "If this should become a stable office workflow, I can propose it for governed HAL memory review—it would not be saved automatically."
)

STABLE_MEMORY_REQUEST_PHRASES = (
    "remember this",
    "save this",
    "add to memory",
    "add this to memory",
    "make this a rule",
    "stable workflow",
    "office workflow",
    "should we always",
)


def _voice_profile(name: str) -> dict[str, object]:
    selected = HAL_VOICE_PROFILES.get(name) or HAL_VOICE_PROFILES["primary"]
    return {
        "lane": str(selected["lane"]),
        "label": str(selected["label"]),
        "tone": str(selected["tone"]),
        "style_notes": [str(item) for item in selected.get("style_notes", [])],
    }


def _governance_note(label: str, detail: str) -> dict[str, str]:
    return {"label": label, "detail": detail}


def _build_governance_notes(*, patient_context_used: bool = False, review_actions_present: bool = False) -> list[dict[str, str]]:
    notes = [
        _governance_note("Data boundary", "HAL stays inside approved local read-only sources and sanitized retrieval."),
        _governance_note("Runtime truthfulness", "HAL only reports runtime, model, file, and tool facts that the backend verified."),
    ]
    if patient_context_used:
        notes.append(
            _governance_note(
                "Patient context",
                "Authorized internal office context may include patient names and matched export rows; the audit trail stores the sanitized request.",
            ),
        )
    if review_actions_present:
        notes.append(
            _governance_note("Human approval", "Requested device or state changes stay pending until a human explicitly approves them."),
        )
    return notes


class CommandRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, callable] = {}
        self._register_defaults()

    def register(self, name: str, func: callable) -> None:
        self._registry[name] = func

    def _register_defaults(self) -> None:
        self.register("backend.rebuild_receipt", run_rebuild_receipt)
        self.register("backend.refresh_and_verify", run_refresh_and_verify)
        self.register("backend.ci_gates", run_ci_gates)
        self.register("backend.smoke_tests", run_smoke_tests)

    def list_registered_backend_commands(self) -> list[str]:
        return sorted(self._registry)

    def execute(self, command_name: str) -> dict[str, object]:
        if command_name not in self._registry:
            raise ValueError(f"Command '{command_name}' is not registered or violates autonomy safety policy.")

        try:
            logger.info("HAL autonomy invoking registered command %s", command_name)
            result = self._registry[command_name]()
            return {
                "status": "success",
                "command": command_name,
                "output": result,
            }
        except Exception as exc:
            logger.exception("HAL autonomy command execution failed for %s", command_name)
            return {
                "status": "failed",
                "command": command_name,
                "error": str(exc),
            }


command_registry = CommandRegistry()


def _load_package_scripts(package_path: Path, *, command_prefix: str, working_directory: str) -> list[dict[str, object]]:
    if not package_path.exists():
        return []

    try:
        package_payload = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    scripts = package_payload.get("scripts")
    if not isinstance(scripts, dict):
        return []

    entries: list[dict[str, object]] = []
    for script_name in sorted(scripts):
        if not isinstance(script_name, str) or not script_name.strip():
            continue
        if SAFE_PACKAGE_SCRIPT_NAME_PATTERN.fullmatch(script_name.strip()) is None:
            continue
        entries.append(
            {
                "command_id": f"{command_prefix}.{script_name}",
                "summary": f"Known npm script '{script_name}' from {working_directory}.",
                "invocation_type": "npm_script",
                "target": f"npm run {script_name}",
                "working_directory": working_directory,
                "category": "npm_script",
                "confirmation_required": False,
            }
        )
    return entries


def _build_hal_shell_registered_commands() -> list[dict[str, object]]:
    project_root = Path(__file__).resolve().parents[2]
    registered_commands: list[dict[str, object]] = [
        {
            "command_id": "backend.rebuild_receipt",
            "summary": "Run the registered rebuild receipt workflow.",
            "invocation_type": "api_endpoint",
            "target": "POST /rebuild",
            "working_directory": ".",
            "category": "registered_command",
            "confirmation_required": False,
        },
        {
            "command_id": "backend.refresh_and_verify",
            "summary": "Run the registered SoftDent refresh and verification workflow.",
            "invocation_type": "api_endpoint",
            "target": "POST /refresh",
            "working_directory": ".",
            "category": "registered_command",
            "confirmation_required": False,
        },
        {
            "command_id": "backend.ci_gates",
            "summary": "Run the registered CI gates workflow.",
            "invocation_type": "api_endpoint",
            "target": "POST /ci-gates",
            "working_directory": ".",
            "category": "registered_command",
            "confirmation_required": False,
        },
        {
            "command_id": "backend.smoke_tests",
            "summary": "Run the registered smoke test workflow.",
            "invocation_type": "api_endpoint",
            "target": "POST /smoke",
            "working_directory": ".",
            "category": "registered_command",
            "confirmation_required": False,
        },
    ]
    registered_commands.extend(
        _load_package_scripts(
            project_root / "package.json",
            command_prefix="npm.root",
            working_directory=".",
        )
    )
    registered_commands.extend(
        _load_package_scripts(
            project_root / "frontend" / "package.json",
            command_prefix="npm.frontend",
            working_directory="frontend",
        )
    )
    return registered_commands


def get_hal_shell_commands(*, command_hint: str | None = None) -> dict[str, object]:
    registered_commands = _build_hal_shell_registered_commands()
    suggested_command_id: str | None = None
    suggestion_reason: str | None = None
    normalized_hint = (command_hint or "").strip()
    if normalized_hint:
        known_ids = [str(entry["command_id"]) for entry in registered_commands]
        matches = difflib.get_close_matches(normalized_hint, known_ids, n=1, cutoff=0.35)
        if matches:
            suggested_command_id = matches[0]
            suggestion_reason = "Nearest registered command ID for the provided hint."

    return {
        "purpose": HAL_SHELL_POLICY_PURPOSE,
        "playbook_active": True,
        "verification_endpoint": HAL_SHELL_VERIFICATION_ENDPOINT,
        "blocked_actions": HAL_SHELL_BLOCKED_ACTIONS[:],
        "confirmation_required_actions": HAL_SHELL_CONFIRMATION_REQUIRED_ACTIONS[:],
        "registered_commands": registered_commands,
        "suggested_command_id": suggested_command_id,
        "suggestion_reason": suggestion_reason,
    }


def _context_flag_enabled(context: dict[str, object], key: str) -> bool:
    value = context.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _load_hal_model_profiles() -> dict[str, object]:
    if not LOCAL_MODEL_PROFILE_CONFIG_PATH.exists():
        return {}
    payload = load_json_file(LOCAL_MODEL_PROFILE_CONFIG_PATH)
    return payload if isinstance(payload, dict) else {}


def _get_hal_model_routing() -> dict[str, object]:
    routing_snapshot = get_model_routing_snapshot()
    frontend = routing_snapshot["frontend"] if isinstance(routing_snapshot.get("frontend"), dict) else {}
    backend = routing_snapshot["backend"] if isinstance(routing_snapshot.get("backend"), dict) else {}
    config = _load_hal_model_profiles()
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    coder_profile = profiles.get("coder") if isinstance(profiles.get("coder"), dict) else {}

    primary_model = str(frontend.get("model") or get_frontend_model_name())
    second_opinion_model = str(backend.get("model") or get_backend_model_name())
    code_model = str(coder_profile.get("model") or second_opinion_model)
    if not code_model or code_model == "unknown":
        code_model = second_opinion_model

    return {
        "primary": {
            "route": "local",
            "model": primary_model,
            "base_url": str(frontend.get("base_url") or get_frontend_base_url()),
            "purpose": "general HAL",
        },
        "second_opinion": {
            "route": "local",
            "model": second_opinion_model,
            "base_url": str(backend.get("base_url") or get_backend_base_url()),
            "purpose": "deeper second opinion",
        },
        "code_help": {
            "route": "local_only_raw_ollama",
            "model": code_model,
            "base_url": str(backend.get("base_url") or get_backend_base_url()),
            "lane": "backend",
            "purpose": "low-risk code_help",
        },
        "optional_test_lane": {
            "route": "local",
            "model": second_opinion_model,
            "purpose": "test-only",
        },
        "truthfulness_boundary": (
            "Report only runtime, file, model, and tool actions that the backend actually verified. "
            "Sensitive, raw, client, and LAN paths remain blocked from raw Ollama."
        ),
    }


def _get_hal_operator_endpoints() -> list[dict[str, str]]:
    return [
        {"path": "/api/hal9000/status", "purpose": "current HAL retrieval, financial, and runtime operating picture"},
        {"path": "/api/hal9000/phases", "purpose": "documented HAL workflow phases"},
        {"path": "/api/hal9000/audits", "purpose": "recent audited HAL activity"},
        {"path": HAL_AUTONOMY_PROFILE_ENDPOINT, "purpose": "autonomy loop, sandbox, and tool-contract profile"},
        {"path": HAL_AUTONOMY_RUNS_ENDPOINT, "purpose": "persisted HAL autonomy runs and think-act-observe state"},
        {"path": "/api/hal/shell/commands", "purpose": "registered-command-only shell policy and safe command registry"},
        {"path": "/api/hal9000/accounting/posting-queue", "purpose": "QuickBooks review queue visibility"},
        {"path": "/api/hal9000/accounting/posting-queue/metrics", "purpose": "QuickBooks review queue counts"},
    ]


def _build_lane_runtime_snapshot(*, base_url: str, lane: str, model: str) -> dict[str, object]:
    cache_key = f"{base_url}:{lane}:{model}"
    if _LANE_RUNTIME_CACHE_SECONDS > 0:
        with _lane_runtime_cache_lock:
            cached = _lane_runtime_cache.get(cache_key)
            if cached and cached[0] > time.monotonic():
                return cached[1]

    runtime_status = get_ollama_runtime_status(base_url, timeout_seconds=2)
    snapshot: dict[str, object] = {
        **runtime_status,
        "lane": lane,
        "model": model,
        "api_reachable": bool(runtime_status.get("api_reachable")),
    }
    if _LANE_RUNTIME_CACHE_SECONDS > 0:
        with _lane_runtime_cache_lock:
            _lane_runtime_cache[cache_key] = (time.monotonic() + _LANE_RUNTIME_CACHE_SECONDS, snapshot)
    return snapshot


def _build_hal_operating_picture(financial_sources: dict[str, object]) -> dict[str, object]:
    frontend_runtime = _build_lane_runtime_snapshot(
        base_url=get_frontend_base_url(),
        lane="frontend",
        model=get_frontend_model_name(),
    )
    backend_runtime = _build_lane_runtime_snapshot(
        base_url=get_backend_base_url(),
        lane="backend",
        model=get_backend_model_name(),
    )
    runtime_status = frontend_runtime
    model_routing = _get_hal_model_routing()
    softdent_status = financial_sources.get("softdent") if isinstance(financial_sources.get("softdent"), dict) else {}
    quickbooks_status = financial_sources.get("quickbooks") if isinstance(financial_sources.get("quickbooks"), dict) else {}
    latest_completion = HAL_COMPLETION_LEDGER[-1] if HAL_COMPLETION_LEDGER else None
    softdent_available = bool(softdent_status.get("available"))
    softdent_period = str(softdent_status.get("period") or "current")
    provider_count = int(softdent_status.get("provider_count") or 0)
    quickbooks_live_revenue = quickbooks_status.get("live_revenue") if isinstance(quickbooks_status.get("live_revenue"), dict) else {}
    quickbooks_health = str(quickbooks_live_revenue.get("health") or "warning")
    latest_completion_clause = (
        f"Latest completed work: {str(latest_completion.get('status') or 'unknown')} ({str(latest_completion.get('entry_id') or 'unknown')})."
        if isinstance(latest_completion, dict)
        else "Latest completed work: none recorded yet."
    )
    frontend_clause = (
        f"Frontend lane is reachable at {frontend_runtime['base_url']} ({frontend_runtime['model']}, {frontend_runtime['model_count']} installed model(s))."
        if frontend_runtime.get("api_reachable")
        else (
            f"Frontend lane is unavailable at {frontend_runtime['base_url']} ({frontend_runtime['model']}): "
            f"{frontend_runtime.get('error') or 'unreachable'}."
        )
    )
    backend_clause = (
        f"Backend lane is reachable at {backend_runtime['base_url']} ({backend_runtime['model']}, {backend_runtime['model_count']} installed model(s))."
        if backend_runtime.get("api_reachable")
        else (
            f"Backend lane is unavailable at {backend_runtime['base_url']} ({backend_runtime['model']}): "
            f"{backend_runtime.get('error') or 'unreachable'}."
        )
    )
    runtime_clause = f"{frontend_clause} {backend_clause}"
    softdent_clause = (
        f"SoftDent aggregates are live for {softdent_period} across {provider_count} provider(s)."
        if softdent_available
        else "SoftDent aggregates are not currently available from the approved local exports."
    )
    summary = (
        "I am local, steady, and working from the backend-verified operating picture. "
        f"{runtime_clause} {softdent_clause} QuickBooks revenue lane health is {quickbooks_health}. "
        f"HAL currently advertises {len(HAL_CAPABILITY_MATRIX)} vetted capabilities across {len(HAL_FILE_OWNERSHIP_AREAS)} file ownership areas. "
        f"{latest_completion_clause}"
    )
    page_field_timeframe_registry = _build_page_field_timeframe_registry(financial_sources)

    return {
        "summary": summary,
        "operator_mode": "deterministic_server_facts_first",
        "local_runtime": runtime_status,
        "frontend_runtime": frontend_runtime,
        "backend_runtime": backend_runtime,
        "local_runtimes": {
            "frontend": frontend_runtime,
            "backend": backend_runtime,
        },
        "capability_matrix": HAL_CAPABILITY_MATRIX[:],
        "file_ownership_areas": HAL_FILE_OWNERSHIP_AREAS[:],
        "completion_ledger": [dict(entry) for entry in HAL_COMPLETION_LEDGER],
        "model_routing": model_routing,
        "developer_operator_endpoints": _get_hal_operator_endpoints(),
        "page_field_timeframe_registry": page_field_timeframe_registry,
    }


def _get_posting_queue_monitor_status() -> dict[str, object]:
    storage_path = get_hal_storage_path()
    metrics = get_accounting_posting_queue_metrics()
    available = storage_path.exists()
    modified_at_utc = (
        datetime.fromtimestamp(storage_path.stat().st_mtime, tz=timezone.utc).isoformat()
        if available
        else ""
    )
    return {
        "available": available,
        "health": "ok" if available else "warning",
        "source_backend": "hal_storage",
        "source_file": storage_path.name,
        "modified_at_utc": modified_at_utc,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "excerpt": (
            f"QuickBooks posting queue storage available with {metrics['pending_review_count']} pending review item(s)."
            if available
            else "QuickBooks posting queue storage is not initialized yet."
        ),
        "review_required": not available,
        "review_flags": [] if available else ["posting queue storage not initialized"],
    }


def _get_local_accounting_documents_monitor_status() -> dict[str, object]:
    documents = list_local_accounting_documents(limit=1)
    items = documents.get("items") if isinstance(documents.get("items"), list) else []
    latest_item = items[0] if items and isinstance(items[0], dict) else {}
    observed_timestamp = str(latest_item.get("processed_at_utc") or "")
    available = bool(items)
    return {
        "available": available,
        "health": "ok" if available else "warning",
        "source_backend": "sqlite",
        "source_file": "hal_local.sqlite3",
        "modified_at_utc": observed_timestamp,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "excerpt": (
            f"Local accounting documents available with {documents.get('count', 0)} indexed document(s)."
            if available
            else "Local accounting documents are not available yet."
        ),
        "review_required": not available,
        "review_flags": [] if available else ["local accounting documents missing"],
    }


def _build_page_field_timeframe_registry(financial_sources: dict[str, object]) -> dict[str, object]:
    evaluated_at = datetime.now(timezone.utc)
    evaluated_at_utc = evaluated_at.isoformat()
    softdent = financial_sources.get("softdent") if isinstance(financial_sources.get("softdent"), dict) else {}
    quickbooks = financial_sources.get("quickbooks") if isinstance(financial_sources.get("quickbooks"), dict) else {}
    posting_queue_monitor = _get_posting_queue_monitor_status()
    accounting_documents_monitor = _get_local_accounting_documents_monitor_status()

    pages = [
        _build_field_timeframe_page(
            page_id="dashboard",
            page_label="Financial Dashboard",
            fields=[
                _build_field_timeframe_field(
                    field_key="summary.production_collections",
                    data_path="financial_summary.monthlyKpis[0]",
                    source_key="softdent.snapshot",
                    max_landing_minutes=30,
                    status=softdent.get("live_snapshot") if isinstance(softdent.get("live_snapshot"), dict) else {},
                    evaluated_at=evaluated_at,
                ),
                _build_field_timeframe_field(
                    field_key="summary.expenses_net_income",
                    data_path="financial_summary.quickBooksProfitLossSummary[0]",
                    source_key="quickbooks.revenue",
                    max_landing_minutes=30,
                    status=quickbooks.get("live_revenue") if isinstance(quickbooks.get("live_revenue"), dict) else {},
                    evaluated_at=evaluated_at,
                ),
            ],
        ),
        _build_field_timeframe_page(
            page_id="admin",
            page_label="Owner Admin",
            fields=[
                _build_field_timeframe_field(
                    field_key="admin.report_pull_status.softdent",
                    data_path="admin_summary.report_pull_status.softdent",
                    source_key="softdent.snapshot",
                    max_landing_minutes=30,
                    status=softdent.get("live_snapshot") if isinstance(softdent.get("live_snapshot"), dict) else {},
                    evaluated_at=evaluated_at,
                ),
                _build_field_timeframe_field(
                    field_key="admin.report_pull_status.quickbooks",
                    data_path="admin_summary.report_pull_status.quickbooks",
                    source_key="quickbooks.revenue",
                    max_landing_minutes=30,
                    status=quickbooks.get("live_revenue") if isinstance(quickbooks.get("live_revenue"), dict) else {},
                    evaluated_at=evaluated_at,
                ),
                _build_field_timeframe_field(
                    field_key="admin.hal_source_review",
                    data_path="hal_status.financial_sources",
                    source_key="softdent.snapshot",
                    max_landing_minutes=30,
                    status=softdent.get("live_snapshot") if isinstance(softdent.get("live_snapshot"), dict) else {},
                    evaluated_at=evaluated_at,
                ),
                _build_field_timeframe_field(
                    field_key="claims.patient_claim_rows",
                    data_path="financial_sources.softdent.live_claims",
                    source_key="softdent.claims",
                    max_landing_minutes=30,
                    status=softdent.get("live_claims") if isinstance(softdent.get("live_claims"), dict) else {},
                    evaluated_at=evaluated_at,
                ),
            ],
        ),
        _build_field_timeframe_page(
            page_id="posting-queue",
            page_label="Posting Queue Review",
            fields=[
                _build_field_timeframe_field(
                    field_key="posting_queue.entries",
                    data_path="posting_queue.items",
                    source_key="posting_queue.storage",
                    max_landing_minutes=30,
                    status=posting_queue_monitor,
                    evaluated_at=evaluated_at,
                ),
                _build_field_timeframe_field(
                    field_key="posting_queue.metrics",
                    data_path="posting_queue.metrics",
                    source_key="posting_queue.storage",
                    max_landing_minutes=30,
                    status=posting_queue_monitor,
                    evaluated_at=evaluated_at,
                ),
            ],
        ),
        _build_field_timeframe_page(
            page_id="accounting-documents",
            page_label="Accounting Documents",
            fields=[
                _build_field_timeframe_field(
                    field_key="accounting_documents.index",
                    data_path="accounting_documents.items",
                    source_key="accounting_documents.sqlite",
                    max_landing_minutes=30,
                    status=accounting_documents_monitor,
                    evaluated_at=evaluated_at,
                ),
                _build_field_timeframe_field(
                    field_key="accounting_documents.review_queue",
                    data_path="accounting_documents.review_required",
                    source_key="accounting_documents.sqlite",
                    max_landing_minutes=30,
                    status=accounting_documents_monitor,
                    evaluated_at=evaluated_at,
                ),
            ],
        ),
    ]

    tracked_field_count = sum(int(page["field_count"]) for page in pages)
    within_window_field_count = sum(int(page["within_window_count"]) for page in pages)
    compliance_percent = round((within_window_field_count / tracked_field_count) * 100, 2) if tracked_field_count else 0.0
    return {
        "evaluated_at_utc": evaluated_at_utc,
        "tracked_field_count": tracked_field_count,
        "within_window_field_count": within_window_field_count,
        "compliance_percent": compliance_percent,
        "pages": pages,
    }


def _build_field_timeframe_page(*, page_id: str, page_label: str, fields: list[dict[str, object]]) -> dict[str, object]:
    within_window_count = sum(1 for field in fields if bool(field.get("within_landing_window")))
    return {
        "page_id": page_id,
        "page_label": page_label,
        "field_count": len(fields),
        "within_window_count": within_window_count,
        "fields": fields,
    }


def _build_field_timeframe_field(
    *,
    field_key: str,
    data_path: str,
    source_key: str,
    max_landing_minutes: int,
    status: dict[str, object],
    evaluated_at: datetime,
) -> dict[str, object]:
    observed_source_timestamp_utc = _field_timeframe_timestamp(status)
    observed_age_minutes = _field_timeframe_age_minutes(observed_source_timestamp_utc, evaluated_at=evaluated_at)
    within_landing_window = observed_age_minutes is not None and observed_age_minutes <= max_landing_minutes
    return {
        "field_key": field_key,
        "data_path": data_path,
        "source_key": source_key,
        "max_landing_minutes": max_landing_minutes,
        "observed_source_timestamp_utc": observed_source_timestamp_utc,
        "observed_age_minutes": observed_age_minutes,
        "within_landing_window": within_landing_window,
    }


def _field_timeframe_timestamp(status: dict[str, object]) -> str:
    if not isinstance(status, dict):
        return ""
    for key in ("modified_at_utc", "checked_at_utc"):
        value = str(status.get(key) or "").strip()
        if value:
            return value
    return ""


def _field_timeframe_age_minutes(timestamp: str, *, evaluated_at: datetime) -> int | None:
    value = str(timestamp or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = evaluated_at - parsed.astimezone(timezone.utc)
    return max(int(round(delta.total_seconds() / 60)), 0)


def _sanitize_hal_export_path(path: Path | str, *, workspace_root: Path | None = None) -> str:
    target = Path(path)
    root = workspace_root or get_ai_workspace_path()
    try:
        relative = target.resolve().relative_to(root.resolve())
    except ValueError:
        return target.name or target.as_posix()
    if not relative.parts:
        return root.name
    return f"{root.name}/{relative.as_posix()}"


def get_hal_operating_picture() -> dict[str, object]:
    return _build_hal_operating_picture(get_financial_source_status())


def _local_ai_journal_workflow_enabled(context: dict[str, object]) -> bool:
    if _context_flag_enabled(context, "use_local_ai_workflow"):
        return True
    env_flag = os.getenv("HAL_ENABLE_LOCAL_JOURNAL_WORKFLOW", "").strip().lower()
    return env_flag in {"1", "true", "yes", "on"}


def _coerce_journal_lines(payload: object, *, description: str) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        raise ValueError("Structured journal payload must include a lines array.")

    normalized_lines: list[dict[str, object]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Journal line {index} must be an object.")
        account_code = str(item.get("account_code") or "").strip()
        account_name = str(item.get("account_name") or "").strip()
        if not account_code or not account_name:
            raise ValueError(f"Journal line {index} is missing account metadata.")
        try:
            debit = round(float(item.get("debit", 0) or 0), 2)
            credit = round(float(item.get("credit", 0) or 0), 2)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Journal line {index} contains a non-numeric debit or credit value.") from exc
        memo = str(item.get("memo") or description).strip() or description
        normalized_lines.append(
            {
                "account_code": account_code,
                "account_name": account_name,
                "debit": debit,
                "credit": credit,
                "memo": memo,
            }
        )
    return normalized_lines


def _build_local_ai_journal_validator(*, chart_of_accounts: dict[str, str], accounting_period: str, description: str):
    open_period = is_period_open(accounting_period)

    def validator(payload: dict[str, object]) -> dict[str, object]:
        lines = _coerce_journal_lines(payload.get("lines"), description=description)
        validation = build_journal_validation(
            lines=lines,
            chart_of_accounts=chart_of_accounts,
            open_period=open_period,
        )
        if (
            not validation["balanced"]
            or not validation["account_validation_passed"]
            or not validation["amount_validation_passed"]
            or not validation["open_period"]
        ):
            return {
                "passed": False,
                "error": "; ".join(validation["issues"]) or "Model-generated journal draft failed validation.",
            }
        payload["lines"] = lines
        payload.setdefault("transaction_type", "model_generated")
        return {
            "passed": True,
            "details": "Structured journal draft passed local accounting validation.",
            "validation": validation,
            "open_period": open_period,
        }

    return validator


def _get_profile_timeout_seconds(profile: dict[str, object], *, default: int = 90) -> int:
    timeout_value = profile.get("timeout_seconds")
    try:
        timeout_seconds = int(timeout_value) if timeout_value is not None else default
    except (TypeError, ValueError):
        timeout_seconds = default
    return max(timeout_seconds, 1)


def _collect_hal_question_context(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    roles: object | None = None,
) -> dict[str, object]:
    state = _get_conversation_state(actor, session_id)
    patient_context = get_controlled_patient_context(question, roles=roles, actor=actor)
    if (not bool(patient_context.get("matched"))) and _is_patient_follow_up_question(question):
        last_patient_name = str(state.get("last_patient_name") or "").strip()
        if last_patient_name:
            patient_context = get_controlled_patient_context(
                f"{question} Patient {last_patient_name}", roles=roles, actor=actor
            )
    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"])
    retrieved_context = retrieve_relevant_context(sanitized_question)
    live_context = get_live_financial_context(sanitized_question)
    hardware_context = compile_hardware_snippets(sanitized_question)
    hardware_review_actions = _build_hardware_review_actions(sanitized_question)
    softdent_aggregate_context = compile_softdent_aggregate_snippets(sanitized_question)
    live_report_context = compile_live_report_snippets(sanitized_question)
    combined_context = [
        *patient_context["snippets"],
        *live_context,
        *hardware_context,
        *softdent_aggregate_context,
        *live_report_context,
        *retrieved_context,
    ]
    if _needs_operating_picture_for_question(question):
        operating_picture = _build_hal_operating_picture(get_financial_source_status())
    else:
        operating_picture = _MINIMAL_OPERATING_PICTURE
    return {
        "state": state,
        "patient_context": patient_context,
        "sanitized": sanitized,
        "sanitized_question": sanitized_question,
        "hardware_context": hardware_context,
        "hardware_review_actions": hardware_review_actions,
        "softdent_aggregate_context": softdent_aggregate_context,
        "live_report_context": live_report_context,
        "combined_context": combined_context,
        "operating_picture": operating_picture,
    }


def _collect_patient_claims_second_opinion_context(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    roles: object | None = None,
) -> dict[str, object]:
    state = _get_conversation_state(actor, session_id)
    patient_context = get_controlled_patient_context(
        question, roles=roles, actor=actor, workflow_reason="second_opinion"
    )
    claim_rows = load_softdent_claim_rows()
    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"])
    patient_snippets = patient_context.get("snippets") if isinstance(patient_context, dict) else []
    combined_context = [_build_claim_export_context_snippet(claim_rows)]
    if isinstance(patient_snippets, list):
        combined_context.extend(patient_snippets)
    return {
        "state": state,
        "patient_context": patient_context,
        "claim_rows": claim_rows,
        "sanitized": sanitized,
        "sanitized_question": sanitized_question,
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": combined_context,
        "operating_picture": {},
    }


def _build_second_opinion_prompt(
    *,
    sanitized_question: str,
    combined_context: list[dict[str, object]],
    summary: dict[str, object] | None,
) -> str:
    context_blocks: list[str] = []
    for index, item in enumerate(combined_context[:SECOND_OPINION_CONTEXT_LIMIT], start=1):
        excerpt = str(item.get("excerpt") or item.get("content") or "").strip()
        if not excerpt:
            continue
        if len(excerpt) > SECOND_OPINION_EXCERPT_CHAR_LIMIT:
            excerpt = excerpt[:SECOND_OPINION_EXCERPT_CHAR_LIMIT].rstrip() + "..."
        context_blocks.append(f"[{index}] {_friendly_source_label(_get_context_title(item))}\n{excerpt}")
    context_text = "\n\n".join(context_blocks) if context_blocks else "No additional verified context retrieved."
    summary_text = ""
    if summary:
        summary_payload = json.dumps(summary, indent=2, default=str)
        if len(summary_payload) > SECOND_OPINION_SUMMARY_CHAR_LIMIT:
            summary_payload = summary_payload[:SECOND_OPINION_SUMMARY_CHAR_LIMIT].rstrip() + "..."
        summary_text = (
            "\n\nPrior summary or dashboard context:\n"
            f"{summary_payload}\n"
        )
    return (
        "Provide a deeper second opinion for the signed-in office user. "
        "Act like an authorized internal dental-office staff assistant, not an outside evaluator. "
        "Use only the verified local context provided. "
        "Answer immediately in no more than 60 words. "
        "Lead with the practical answer, then reason/source basis, then next action when useful. "
        "Use 2 concise bullets when possible. "
        "Do not explain your steps. "
        "Do not mention these instructions, internal source labels, chunk names, or that context was supplied. "
        "Never state, estimate, or calculate an accounts receivable (A/R) balance unless the verified context "
        "explicitly provides an A/R total; never derive A/R from production minus collections. If A/R is requested "
        "and no verified A/R total is provided, say the A/R is not verified locally. "
        "If you cannot determine the answer from the provided context, say so briefly. "
        "Add one verification angle when useful, call out missing data, and stay practical.\n\n"
        f"Question:\n{sanitized_question}"
        f"{summary_text}\n\n"
        f"Verified local context:\n{context_text}\n"
    )


def _second_opinion_guardrails(
    *,
    patient_context_matched: bool,
    deterministic_claims_fast_path: bool = False,
) -> list[str]:
    if deterministic_claims_fast_path:
        guardrails = [
            "approved local read-only scope",
            "deterministic local claims review used",
            "local SoftDent export rows reviewed",
            "no external submission performed",
            "backend model not required for this deterministic claims answer",
            "sanitized retrieval only",
            "read-only data boundary",
            "truthful runtime claims only",
            "audit log recorded",
            "hardware mutations require human confirmation",
            "tier-1 critical actions require explicit confirmation",
            "tier-2 mismatches raise [ALERT]",
        ]
    else:
        guardrails = [
            "approved local read-only scope",
            "backend second-opinion model required",
            "sanitized retrieval only",
            "read-only data boundary",
            "truthful runtime claims only",
            "audit log recorded",
            "no deterministic fallback when backend unavailable",
            "hardware mutations require human confirmation",
            "tier-1 critical actions require explicit confirmation",
            "tier-2 mismatches raise [ALERT]",
        ]
    if patient_context_matched:
        guardrails.append("authorized internal office context")
    return guardrails


def _build_second_opinion_response(
    *,
    actor: str,
    question: str,
    session_id: str | None,
    context_bundle: dict[str, object],
    answer: str,
    local_ai_unavailable: str | None = None,
    deterministic_claims_fast_path: bool = False,
    claims_audit_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    patient_context = context_bundle["patient_context"]
    if not isinstance(patient_context, dict):
        patient_context = {}
    sanitized = context_bundle["sanitized"]
    if not isinstance(sanitized, dict):
        sanitized = {"findings": []}
    sanitized_question = str(context_bundle["sanitized_question"])
    combined_context = context_bundle["combined_context"]
    if not isinstance(combined_context, list):
        combined_context = []
    hardware_review_actions = context_bundle["hardware_review_actions"]
    if not isinstance(hardware_review_actions, list):
        hardware_review_actions = []
    softdent_aggregate_context = context_bundle["softdent_aggregate_context"]
    if not isinstance(softdent_aggregate_context, list):
        softdent_aggregate_context = []
    state = context_bundle["state"]
    if not isinstance(state, dict):
        state = {}

    _update_conversation_state(
        actor=actor,
        session_id=session_id,
        state=state,
        question=question,
        patient_context=patient_context,
        softdent_aggregate_context=softdent_aggregate_context,
        hardware_review_actions=hardware_review_actions,
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="hal-second-opinion",
        detail=(
            f"Second opinion unavailable for sanitized request: {sanitized_question[:140]}"
            if local_ai_unavailable
            else f"Answered a HAL second-opinion request for sanitized request: {sanitized_question[:140]}"
        ),
    )
    answer = _append_governed_memory_proposal(answer, question=question)
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:second-opinion",
        sanitized_question=sanitized_question,
        retrieval_ids=[_get_context_source_id(item) for item in combined_context if isinstance(item, dict)],
        response_summary=_build_second_opinion_audit_summary(
            answer,
            deterministic_claims_fast_path=deterministic_claims_fast_path,
            claims_audit_meta=claims_audit_meta,
        ),
    )
    patient_matched = bool(patient_context.get("matched"))
    return {
        "mode": f"{HAL_MODE}:second-opinion",
        "answer": answer,
        "local_ai_unavailable": local_ai_unavailable,
        "sanitized_question": sanitized_question,
        "sanitization_findings": sanitized.get("findings", []),
        "retrieved_context": combined_context,
        "guardrails": _second_opinion_guardrails(
            patient_context_matched=patient_matched,
            deterministic_claims_fast_path=deterministic_claims_fast_path,
        ),
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "review_actions": hardware_review_actions,
        "voice_profile": _voice_profile("second_opinion"),
        "governance_notes": _build_governance_notes(
            patient_context_used=patient_matched,
            review_actions_present=bool(hardware_review_actions),
        ),
    }


def _format_backend_lane_unavailable_message(error: LocalAIConfigError | None = None) -> str:
    base_url = get_backend_base_url()
    model_name = get_backend_model_name()
    detail = str(error).strip() if error else "Start the backend model server or configure AI_BACKEND_BASE_URL / AI_BACKEND_MODEL."
    return (
        f"Backend local AI lane unavailable at {base_url} for {model_name}. "
        f"{detail}"
    )


def _try_local_ai_journal_draft(
    *,
    description: str,
    accounting_period: str,
    amount: float,
    context: dict[str, object],
) -> dict[str, object] | None:
    if not _local_ai_journal_workflow_enabled(context):
        return None
    if not LOCAL_MODEL_PROFILE_CONFIG_PATH.exists():
        return {"local_ai_unavailable": "Local model profile config is missing; using rule-based journal draft fallback."}

    try:
        require_lane_runtime("coder", purpose="journal draft structured parsing")
    except LocalAIConfigError as exc:
        return {"local_ai_unavailable": _format_backend_lane_unavailable_message(exc)}

    try:
        config = load_local_model_profile_config()
    except Exception as exc:
        return {"local_ai_unavailable": f"Local model profile config could not be loaded: {exc}"}

    parser_profile = resolve_lane_profile(config, "coder")
    narrator_profile = resolve_lane_profile(config, "chat")
    chart_of_accounts = get_chart_of_accounts()
    validator = _build_local_ai_journal_validator(
        chart_of_accounts=chart_of_accounts,
        accounting_period=accounting_period,
        description=description,
    )
    source_text = str(context.get("source_text") or description)
    try:
        workflow_result = run_structured_output_workflow(
            base_url=get_backend_base_url(),
            parser_base_url=get_backend_base_url(),
            narrator_base_url=get_frontend_base_url(),
            parser_profile=parser_profile,
            narrator_profile=narrator_profile,
            source_text=source_text,
            parse_instructions=(
                "Infer the accounting transaction type and return a JSON object with keys transaction_type and lines. "
                "The lines array must contain balanced debit and credit entries using only the approved chart of accounts. "
                f"Use this exact amount for the full entry total: {amount:.2f}."
            ),
            summary_instructions=(
                "Summarize the validated journal draft in one sentence for a human accounting reviewer. "
                "Mention whether the draft is balanced and that human review is still required."
            ),
            timeout_seconds=20,
            required_keys=["transaction_type", "lines"],
            validator=validator,
            seed=parser_profile.get("seed"),
        )
    except Exception as exc:
        return {"local_ai_unavailable": f"Backend local AI journal workflow failed: {exc}"}

    return {
        "lines": workflow_result["parsed_payload"]["lines"],
        "summary": str(workflow_result["summary_text"]),
        "transaction_type": str(workflow_result["parsed_payload"].get("transaction_type") or "model_generated"),
    }


def get_hal_access_policy() -> dict[str, object]:
    workspace_root = get_ai_workspace_path()
    return {
        "mode": HAL_MODE,
        "auth_requirement": "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required. Promote to stronger identity controls before any real production model access.",
        "network_boundary": "Local-only backend mediation; no direct browser-to-model access, and HAL-managed writes stay inside AI_Workspace.",
        "audited": True,
        "workspace_root": _sanitize_hal_export_path(workspace_root, workspace_root=workspace_root),
        "activity_log_path": _sanitize_hal_export_path(get_ai_activity_log_path(), workspace_root=workspace_root),
        "review_plan_directory": _sanitize_hal_export_path(get_ai_review_plan_directory(), workspace_root=workspace_root),
        "allowed_sources": [
            "calculated_kpis",
            "sanitized_financial_summaries",
            "softdent_aggregate_snapshots",
            "sanitized_softdent_claim_exports",
            "sanitized_softdent_clinical_note_exports",
            "reviewed_patient_specific_softdent_exports",
            "approved_quickbooks_summary_queries",
            "internal_policy_docs",
            "AI_Workspace allowlisted HAL artifacts",
        ],
        "disallowed_actions": [
            "raw_phi_prompting",
            "arbitrary_sql",
            "production_writes",
            "unreviewed_external_model_calls",
            "free_form_shell_commands",
            "process_state_commands_without_confirmation",
            "quickbooks_write_or_apply_commands",
            "secret_printing",
            "filesystem_access_outside_ai_workspace",
        ],
        "capability_hierarchy": [dict(rule) for rule in HAL_CAPABILITY_HIERARCHY],
    }


def get_hal_phases() -> list[str]:
    return HAL_PHASES[:]


def refresh_local_hal_index(*, actor: str) -> dict[str, object]:
    metadata = refresh_hal_index()
    return {
        "message": f"HAL index refreshed for {actor}",
        "document_count": metadata["document_count"],
        "source_count": metadata["source_count"],
        "refreshed_at_utc": metadata["refreshed_at_utc"],
        "storage_path": _sanitize_hal_export_path(str(metadata["storage_path"])),
        "vector_path": _sanitize_hal_export_path(str(metadata["vector_path"])),
        "backend": metadata["backend"],
        "embedding_provider": metadata["embedding_provider"],
        "mode": HAL_MODE,
    }


def get_hal_index_status() -> dict[str, object]:
    financial_sources = get_financial_source_status()
    return {
        "mode": HAL_MODE,
        "document_count": count_hal_collection_documents(),
        "storage_path": _sanitize_hal_export_path(get_hal_storage_path()),
        "vector_path": _sanitize_hal_export_path(get_hal_chroma_path()),
        "backend": "chroma",
        "embedding_provider": get_embedding_provider_name(),
        "financial_sources": financial_sources,
        "operating_picture": _build_hal_operating_picture(financial_sources),
    }


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_hal_autonomy_profile() -> dict[str, object]:
    registered_commands = _build_hal_shell_registered_commands()
    return {
        "mode": HAL_MODE,
        "execution_loop": {
            "enabled": True,
            "loop_mode": HAL_AUTONOMY_LOOP_MODE,
            "cycle": ["think", "choose_approved_tool", "observe", "persist_state", "repeat"],
            "default_max_steps": HAL_AUTONOMY_DEFAULT_MAX_STEPS,
            "max_steps_cap": HAL_AUTONOMY_MAX_STEPS,
            "advance_endpoint": f"{HAL_AUTONOMY_RUNS_ENDPOINT}/{{run_id}}/advance",
        },
        "function_calling": {
            "enabled": True,
            "tool_registry_endpoint": HAL_SHELL_VERIFICATION_ENDPOINT,
            "backend_tool_ids": ["hal.status", "hal.shell_commands", "hal.refresh_index", "hal.execute_registered_command"],
            "registered_command_count": len(registered_commands),
            "mcp_tools_endpoint": "/api/v1/mcp/tools",
            "mcp_call_endpoint": "/api/v1/mcp/tools/call",
            "policy": "HAL can only call reviewed backend tools or registered commands exposed by the backend policy surface.",
        },
        "sandbox": {
            "mode": HAL_AUTONOMY_SANDBOX_MODE,
            "working_directory": HAL_AUTONOMY_WORKING_DIRECTORY,
            "network_boundary": "local-only backend mediation",
            "writes_blocked": True,
            "shell_policy": "registered-command-only",
        },
        "state_management": {
            "enabled": True,
            "backend": "sqlite",
            "storage_path": _sanitize_hal_export_path(get_hal_storage_path()),
            "runs_endpoint": HAL_AUTONOMY_RUNS_ENDPOINT,
            "list_endpoint": HAL_AUTONOMY_RUNS_ENDPOINT,
        },
    }


def _guess_shell_command_hint(objective: str) -> str | None:
    lowered = objective.lower()
    if "refresh" in lowered and "verify" in lowered:
        return "backend.refresh_and_verify"
    if "test" in lowered or "smoke" in lowered:
        return "backend.smoke_tests"
    if "ci" in lowered or "gate" in lowered:
        return "backend.ci_gates"
    return None


def _build_hal_autonomy_plan(objective: str) -> list[dict[str, object]]:
    lowered = objective.lower()
    plan: list[dict[str, object]] = []
    command_hint = _guess_shell_command_hint(objective)

    if "refresh" in lowered or "index" in lowered:
        plan.append(
            {
                "title": "Refresh approved HAL retrieval index",
                "tool_name": "hal.refresh_index",
                "reason": "Objective mentions refresh or index management.",
                "tool_input": {},
            }
        )

    if any(term in lowered for term in ("status", "runtime", "operating picture", "health", "model")) or not plan:
        plan.append(
            {
                "title": "Capture backend-verified HAL status",
                "tool_name": "hal.status",
                "reason": "Objective needs current verified runtime or financial state.",
                "tool_input": {},
            }
        )

    if any(term in lowered for term in ("shell", "command", "workflow", "verify", "script")) or not plan:
        tool_input: dict[str, object] = {}
        if command_hint:
            tool_input["command_hint"] = command_hint
        plan.append(
            {
                "title": "Inspect approved command registry",
                "tool_name": "hal.shell_commands",
                "reason": "Objective needs allowed tool execution paths before any autonomous action.",
                "tool_input": tool_input,
            }
        )

    if command_hint:
        plan.append(
            {
                "title": f"Execute registered command {command_hint}",
                "tool_name": "hal.execute_registered_command",
                "reason": "Objective matches a vetted backend workflow that can be executed inside the approved autonomy sandbox.",
                "tool_input": {"command_id": command_hint},
            }
        )

    plan.append(
        {
            "title": "Summarize verified progress",
            "tool_name": "hal.complete",
            "reason": "Close the loop after approved tools have been observed.",
            "tool_input": {},
        }
    )
    return plan


def _serialize_hal_autonomy_run(run: dict[str, object]) -> dict[str, object]:
    current_step = int(run.get("current_step") or 0)
    plan = run.get("plan") if isinstance(run.get("plan"), list) else []
    next_action = dict(plan[current_step]) if current_step < len(plan) and isinstance(plan[current_step], dict) else {}
    return {
        **run,
        "next_action": next_action,
        "activity_count": len(run.get("activity") if isinstance(run.get("activity"), list) else []),
    }


def _summarize_hal_autonomy_tool_result(tool_name: str, payload: dict[str, object]) -> str:
    if tool_name == "hal.status":
        operating_picture = payload.get("operating_picture") if isinstance(payload.get("operating_picture"), dict) else {}
        return str(operating_picture.get("summary") or "Collected verified HAL status.")
    if tool_name == "hal.shell_commands":
        commands = payload.get("registered_commands") if isinstance(payload.get("registered_commands"), list) else []
        suggested = payload.get("suggested_command_id")
        if suggested:
            return f"Observed {len(commands)} registered commands. Suggested command: {suggested}."
        return f"Observed {len(commands)} registered commands under the approved shell policy."
    if tool_name == "hal.refresh_index":
        document_count = int(payload.get("document_count") or 0)
        source_count = int(payload.get("source_count") or 0)
        return f"Refreshed HAL index with {document_count} documents from {source_count} approved sources."
    if tool_name == "hal.execute_registered_command":
        status = str(payload.get("status") or "unknown")
        command_name = str(payload.get("command") or "unknown")
        if status == "success":
            output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
            summary_keys = ", ".join(sorted(output.keys())[:5]) if output else "no structured keys"
            return f"Executed {command_name} successfully. Output included {summary_keys}."
        return f"Execution failed for {command_name}: {payload.get('error') or 'unknown error'}."
    return "Completed approved HAL tool call."


def _execute_hal_autonomy_tool(*, tool_name: str, tool_input: dict[str, object], actor: str) -> dict[str, object]:
    if tool_name == "hal.status":
        return get_hal_index_status()
    if tool_name == "hal.shell_commands":
        command_hint = tool_input.get("command_hint")
        return get_hal_shell_commands(command_hint=str(command_hint) if isinstance(command_hint, str) else None)
    if tool_name == "hal.refresh_index":
        return refresh_local_hal_index(actor=actor)
    if tool_name == "hal.execute_registered_command":
        command_id = tool_input.get("command_id")
        if not isinstance(command_id, str) or not command_id.strip():
            raise ValueError("Registered command execution requires a command_id.")
        return command_registry.execute(command_id.strip())
    raise ValueError(f"Unsupported HAL autonomy tool: {tool_name}")


def create_hal_autonomy_run(*, objective: str, actor: str, max_steps: int = HAL_AUTONOMY_DEFAULT_MAX_STEPS) -> dict[str, object]:
    bounded_max_steps = max(1, min(max_steps, HAL_AUTONOMY_MAX_STEPS))
    sanitized = sanitize_hal_text(objective)
    now = _now_utc_iso()
    run = {
        "run_id": f"hal-run-{uuid4().hex[:12]}",
        "created_at_utc": now,
        "updated_at_utc": now,
        "actor": actor,
        "objective": objective,
        "sanitized_objective": str(sanitized["sanitized_text"]),
        "status": "queued",
        "max_steps": bounded_max_steps,
        "current_step": 0,
        "sandbox_mode": HAL_AUTONOMY_SANDBOX_MODE,
        "working_directory": HAL_AUTONOMY_WORKING_DIRECTORY,
        "loop_mode": HAL_AUTONOMY_LOOP_MODE,
        "plan": _build_hal_autonomy_plan(objective),
        "activity": [],
        "completion_summary": None,
    }
    save_hal_autonomy_run(run)
    return _serialize_hal_autonomy_run(run)


def get_hal_autonomy_run_status(*, run_id: str) -> dict[str, object]:
    run = get_hal_autonomy_run(run_id)
    if run is None:
        raise LookupError("HAL autonomy run was not found.")
    return _serialize_hal_autonomy_run(run)


def list_hal_autonomy_runs(*, limit: int = 10) -> dict[str, object]:
    runs = [_serialize_hal_autonomy_run(item) for item in get_recent_hal_autonomy_runs(limit=limit)]
    return {
        "count": len(runs),
        "items": runs,
    }


def advance_hal_autonomy_run(*, run_id: str, actor: str, cycles: int = 1) -> dict[str, object]:
    run = get_hal_autonomy_run(run_id)
    if run is None:
        raise LookupError("HAL autonomy run was not found.")

    bounded_cycles = max(1, min(cycles, 5))
    if str(run.get("status")) in {"completed", "blocked"}:
        return _serialize_hal_autonomy_run(run)

    plan = run.get("plan") if isinstance(run.get("plan"), list) else []
    activity = run.get("activity") if isinstance(run.get("activity"), list) else []
    current_step = int(run.get("current_step") or 0)
    max_steps = int(run.get("max_steps") or HAL_AUTONOMY_DEFAULT_MAX_STEPS)

    for _ in range(bounded_cycles):
        if current_step >= len(plan):
            run["status"] = "completed"
            run["completion_summary"] = "HAL autonomy run completed all planned approved steps."
            break

        if current_step >= max_steps:
            run["status"] = "blocked"
            run["completion_summary"] = "HAL autonomy run exhausted its step budget before completing the plan."
            break

        step = plan[current_step] if isinstance(plan[current_step], dict) else {}
        tool_name = str(step.get("tool_name") or "")
        title = str(step.get("title") or f"Step {current_step + 1}")
        reason = str(step.get("reason") or "")
        tool_input = step.get("tool_input") if isinstance(step.get("tool_input"), dict) else {}

        if tool_name == "hal.complete":
            current_step += 1
            run["status"] = "completed"
            run["completion_summary"] = "HAL autonomy run completed all planned approved steps."
            activity.append(
                {
                    "step_index": current_step,
                    "title": title,
                    "thought": "Enough approved observations were collected to close this run.",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "observation": "Marked the run complete without invoking any additional tool.",
                    "status": "completed",
                    "recorded_at_utc": _now_utc_iso(),
                }
            )
            break

        thought = f"{reason} Executing approved tool {tool_name} from the HAL autonomy sandbox."
        observation_payload = _execute_hal_autonomy_tool(tool_name=tool_name, tool_input=tool_input, actor=actor)
        observation = _summarize_hal_autonomy_tool_result(tool_name, observation_payload)
        current_step += 1
        activity.append(
            {
                "step_index": current_step,
                "title": title,
                "thought": thought,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "observation": observation,
                "status": "completed",
                "recorded_at_utc": _now_utc_iso(),
            }
        )
        run["status"] = "running" if current_step < len(plan) else "completed"
        if run["status"] == "completed":
            run["completion_summary"] = "HAL autonomy run completed all planned approved steps."
            break

    run["current_step"] = current_step
    run["activity"] = activity
    run["updated_at_utc"] = _now_utc_iso()
    save_hal_autonomy_run(run)
    return _serialize_hal_autonomy_run(run)


def list_hal_audit_events(limit: int) -> dict[str, object]:
    audits = get_recent_hal_audits(limit=limit)
    return {
        "count": len(audits),
        "items": audits,
    }


def list_accounting_posting_queue(*, limit: int, cursor: str | None, status: str | None) -> dict[str, object]:
    items, total_count, next_cursor, range_start, range_end = get_recent_accounting_posting_queue_entries(limit=limit, cursor=cursor, status=status)
    return {
        "count": len(items),
        "total_count": total_count,
        "limit": limit,
        "cursor": cursor,
        "next_cursor": next_cursor,
        "range_start": range_start,
        "range_end": range_end,
        "status": status,
        "items": items,
    }


def get_accounting_posting_queue_summary() -> dict[str, int]:
    return get_accounting_posting_queue_metrics()


def list_recent_accounting_posting_queue_activity(limit: int) -> dict[str, object]:
    items = get_recent_accounting_posting_queue_activity(limit=limit)
    return {
        "count": len(items),
        "limit": limit,
        "items": items,
    }


def review_accounting_posting_queue_entry(
    *,
    queue_id: str,
    action: PostingQueueReviewAction,
    review_note: str | None,
    actor: str,
) -> dict[str, object]:
    entry = get_accounting_posting_queue_entry(queue_id)
    if entry is None:
        raise LookupError("Posting queue entry was not found.")
    if entry["status"] != POSTING_QUEUE_STATUS_PENDING_REVIEW:
        raise ValueError("Only pending review queue entries can be approved or rejected.")

    reviewed_at_utc = datetime.now(timezone.utc).isoformat()
    update_accounting_posting_queue_review(
        queue_id=queue_id,
        status=action,
        reviewer_actor=actor,
        reviewed_at_utc=reviewed_at_utc,
        review_note=review_note.strip() if isinstance(review_note, str) and review_note.strip() else None,
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:posting-queue-review",
        sanitized_question=entry["description"],
        retrieval_ids=[queue_id, entry["source_audit_id"]],
        response_summary=f"{action.title()} QuickBooks Desktop posting queue entry {queue_id}."[:180],
    )
    updated_entry = get_accounting_posting_queue_entry(queue_id)
    if updated_entry is None:
        raise LookupError("Posting queue entry could not be reloaded after review.")
    append_ai_activity_log(
        tier="tier_1",
        actor=actor,
        action=f"posting-queue-{action}",
        detail=f"{action.title()} QuickBooks Desktop posting queue entry {queue_id}.",
    )
    updated_entry["audit_id"] = audit_entry["audit_id"]
    return updated_entry


def _should_include_context_excerpt_in_answer(item: dict[str, object], excerpt: str) -> bool:
    title = _get_context_title(item)
    if re.fullmatch(r"(?i)readme chunk \d+", title.strip()):
        return False
    if "localhost:5173/app" in excerpt.lower():
        return False
    return True


def _is_documentation_context_item(item: dict[str, object]) -> bool:
    category = str(item.get("category") or "").strip().lower()
    source_id = _get_context_source_id(item).lower()
    title = _get_context_title(item).lower()
    if category in {"documentation", "docs", "developer_note", "developer_notes"}:
        return True
    doc_markers = ("readme", "docs", "documentation", "dashboard doc", "route doc", "ui documentation")
    return any(marker in source_id or marker in title for marker in doc_markers)


def _is_source_health_diagnostic_context_item(item: dict[str, object]) -> bool:
    category = str(item.get("category") or "").strip().lower()
    source_id = _get_context_source_id(item).lower()
    title = _get_context_title(item).lower()
    excerpt = str(item.get("excerpt") or item.get("content") or "").lower()
    if category in {"source_health", "source_diagnostic", "diagnostics"}:
        return True
    diagnostic_markers = (
        "sdk summary is currently unavailable",
        "sdk summary is unavailable",
        "qbxml",
        "modal dialog",
        "source-health",
        "source health",
        "diagnostic",
    )
    return any(marker in source_id or marker in title or marker in excerpt for marker in diagnostic_markers)


def _is_verified_operational_context_item(item: dict[str, object]) -> bool:
    if _is_documentation_context_item(item) or _is_source_health_diagnostic_context_item(item):
        return False
    category = str(item.get("category") or "").strip().lower()
    source_id = _get_context_source_id(item).lower()
    title = _get_context_title(item).lower()
    operational_categories = {
        "softdent_aggregate",
        "softdent_tool",
        "softdent_claims",
        "softdent_clinical_notes",
        "patient_context",
        "claim_context",
        "office_task",
        "local_task",
        "report",
        "financial_report",
    }
    if category in operational_categories:
        return True
    operational_markers = (
        "softdent-live",
        "softdent-claims",
        "softdent-clinical",
        "claim",
        "clinical",
        "patient",
        "daysheet",
        "end-of-day",
        "eod",
        "draft",
        "task",
        "blocked",
        "qb-",
    )
    return any(marker in source_id or marker in title for marker in operational_markers)


def _build_context_excerpt_summary(items: list[dict[str, object]], *, limit: int = 2) -> str:
    prioritized_items = sorted(
        items,
        key=lambda item: 1 if _is_documentation_context_item(item) else 0,
    )
    excerpts: list[str] = []
    seen: set[str] = set()
    for item in prioritized_items:
        if str(item.get("category") or "") == "softdent_aggregate":
            continue
        excerpt = str(item.get("excerpt") or "").strip()
        if not excerpt or excerpt.startswith("#") or excerpt in seen:
            continue
        if not _should_include_context_excerpt_in_answer(item, excerpt):
            continue
        seen.add(excerpt)
        excerpts.append(excerpt)
        if len(excerpts) >= limit:
            break
    return " ".join(excerpts)


def _get_context_source_id(item: dict[str, object]) -> str:
    source_id = str(item.get("source_id") or "").strip()
    if source_id:
        return source_id
    title = str(item.get("title") or "").strip()
    if title:
        return title
    return "approved-local-context"


def _get_context_title(item: dict[str, object]) -> str:
    title = str(item.get("title") or "").strip()
    if title:
        return title
    return _get_context_source_id(item)


def _build_report_answer_summary(items: list[dict[str, str]], *, limit: int = 2) -> str:
    excerpts: list[str] = []
    for item in items:
        source_id = str(item.get("source_id") or "")
        if not source_id.startswith("qb-"):
            continue
        excerpt = str(item.get("excerpt") or "").strip()
        if not excerpt:
            continue
        excerpts.append(excerpt)
        if len(excerpts) >= limit:
            break
    return " ".join(excerpts)


def _build_hardware_answer_summary(items: list[dict[str, str]], *, limit: int = 1) -> str:
    excerpts: list[str] = []
    for item in items:
        if str(item.get("category") or "") != "hardware_status":
            continue
        if str(item.get("source_id") or "") == "physical_monitor_primary":
            brightness = item.get("brightness")
            contrast = item.get("contrast")
            input_source = str(item.get("input_source") or "Unknown/Unsupported")
            excerpts.append(f"Brightness={brightness}% | Contrast={contrast}% | Input={input_source}")
        else:
            excerpt = str(item.get("excerpt") or "").strip()
            if excerpt:
                excerpts.append(excerpt)
        if len(excerpts) >= limit:
            break
    return " ".join(excerpts)


def _build_hardware_review_actions(sanitized_question: str) -> list[dict[str, object]]:
    intent = build_monitor_mutation_intent(sanitized_question)
    if intent is None:
        return []

    target_value = int(intent["target_value"])
    return [
        {
            "action_id": f"monitor-set-luminance-{target_value}",
            "action_type": str(intent["action_type"]),
            "target_device": "primary_monitor",
            "target_value": target_value,
            "human_review_required": bool(intent["human_review_required"]),
            "status": "pending_confirmation",
            "title": f"Set monitor brightness to {target_value}%",
            "confirmation_message": f"Review before sending a DDC/CI brightness change to {target_value}%.",
        }
    ]


def _build_softdent_answer_summary(items: list[dict[str, str]], *, limit: int = 2) -> str:
    excerpts: list[str] = []
    for item in items:
        if str(item.get("category") or "") != "softdent_aggregate":
            continue
        if str(item.get("source_id") or "") == "softdent-live-summary":
            production = _format_currency(item.get("total_production"))
            collections = _format_currency(item.get("total_collections"))
            ratio = str(item.get("collection_ratio") or "0.00")
            excerpts.append(f"Production={production} | Collections={collections} ({ratio}% Collection Ratio)")
            if len(excerpts) >= limit:
                break
            continue
        if str(item.get("source_id") or "") == "softdent-live-provider-ranking":
            provider_name = str(item.get("top_provider_name") or "Unknown")
            production = _format_currency(item.get("top_provider_production"))
            excerpts.append(f"Top Provider={provider_name} ({production} Production)")
            if len(excerpts) >= limit:
                break
            continue
        if str(item.get("source_id") or "") == "softdent-live-payer-mix":
            insurance_total = _format_currency(item.get("insurance_total"))
            patient_total = _format_currency(item.get("patient_total"))
            insurance_share = str(item.get("insurance_share") or "0.00")
            patient_share = str(item.get("patient_share") or "0.00")
            excerpts.append(
                f"Insurance={insurance_total} ({insurance_share}%) | Patient={patient_total} ({patient_share}%)"
            )
            if len(excerpts) >= limit:
                break
            continue
        if str(item.get("source_id") or "") == "softdent-live-collection-delta":
            delta = _format_currency(item.get("collection_delta"))
            ratio = str(item.get("collection_ratio") or "0.00")
            excerpts.append(f"Collection Delta={delta} ({ratio}% Collection Ratio)")
            if len(excerpts) >= limit:
                break
            continue
        excerpt = str(item.get("excerpt") or "").strip()
        if not excerpt:
            continue
        excerpts.append(excerpt)
        if len(excerpts) >= limit:
            break
    return " ".join(excerpts)


def _build_patient_context_summary(patient_context: dict[str, object]) -> str:
    if not bool(patient_context.get("matched")):
        return ""

    summary_fields = patient_context.get("summary_fields") if isinstance(patient_context.get("summary_fields"), dict) else {}
    patient_name = str(summary_fields.get("patient_name") or "the patient")
    claim_count = int(summary_fields.get("claim_count") or 0)
    note_count = int(summary_fields.get("note_count") or 0)
    total_claim_amount = _format_currency(summary_fields.get("total_claim_amount"))
    primary_status = str(summary_fields.get("primary_claim_status") or "under review")
    parts = [f"Patient={patient_name}"]
    if claim_count:
        parts.append(f"Claims={claim_count} ({total_claim_amount} total)")
        parts.append(f"Primary Status={primary_status}")
    if note_count:
        parts.append(f"Clinical Notes={note_count}")
    return " | ".join(parts)


def _normalize_conversation_session_id(actor: str, session_id: str | None) -> str:
    normalized = str(session_id or "").strip()
    return normalized or actor


def _get_conversation_state(actor: str, session_id: str | None = None) -> dict[str, object]:
    state = get_hal_conversation_state(actor, _normalize_conversation_session_id(actor, session_id))
    return state if isinstance(state, dict) else {}


def _save_conversation_state(actor: str, session_id: str | None, state: dict[str, object]) -> None:
    save_hal_conversation_state(
        actor=actor,
        session_id=_normalize_conversation_session_id(actor, session_id),
        state=state,
    )


def _is_follow_up_question(question: str) -> bool:
    lowered = question.lower()
    return any(phrase in lowered for phrase in FOLLOW_UP_PHRASES)


def _is_patient_follow_up_question(question: str) -> bool:
    lowered = question.lower()
    return "patient" in lowered or "follow-up plan" in lowered or "follow up plan" in lowered or "do not switch patients" in lowered


def _is_patient_claims_second_opinion_question(question: str) -> bool:
    lowered = question.lower()
    return any(
        keyword in lowered
        for keyword in (
            "patient",
            "claim",
            "claims",
            "denial",
            "denied",
            "insurance",
            "payer",
            "appeal",
            "resubmission",
            "attachment",
            "narrative",
            "procedure",
        )
    )


def _claim_field(row: dict[str, object], key: str) -> str:
    for row_key, value in row.items():
        if row_key.lower() == key.lower() and value not in (None, ""):
            return str(value)
    return ""


def _claim_amount(row: dict[str, object]) -> float:
    try:
        return float(_claim_field(row, "ClaimAmount") or 0)
    except ValueError:
        return 0.0


def _claim_status(row: dict[str, object]) -> str:
    return _claim_field(row, "ClaimStatus") or "Unknown"


def _is_open_claim(row: dict[str, object]) -> bool:
    return _claim_status(row).strip().lower() not in {"paid", "closed", "complete", "completed"}


def _format_claim_row(row: dict[str, object]) -> str:
    claim_id = _claim_field(row, "ClaimId") or "unknown claim"
    patient = _claim_field(row, "PatientName") or "unknown patient"
    status = _claim_status(row)
    payer = _claim_field(row, "Payer") or "unknown payer"
    amount = _format_currency(_claim_amount(row))
    procedure = _claim_field(row, "Procedure")
    reason = _claim_field(row, "DenialReason")
    parts = [f"{claim_id}: {patient}", f"status {status}", f"payer {payer}", f"amount {amount}"]
    if procedure:
        parts.append(f"procedure {procedure}")
    if reason:
        parts.append(f"note {reason.rstrip('.')}")
    return "; ".join(parts)


def _build_claim_export_context_snippet(claim_rows: list[dict[str, object]]) -> dict[str, object]:
    if not claim_rows:
        excerpt = "SoftDent claims export was checked but no readable claim rows were available."
    else:
        formatted_rows = [_format_claim_row(row) for row in claim_rows[:5]]
        excerpt = "SoftDent claims export summary: " + " | ".join(formatted_rows)
    return {
        "source_id": "softdent-claims-export-second-opinion",
        "title": "SoftDent claims export second-opinion source",
        "category": "softdent_tool",
        "excerpt": excerpt,
    }


def _claim_rows_for_question(question: str, claim_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], str]:
    lowered = question.lower()
    open_rows = [row for row in claim_rows if _is_open_claim(row)]
    denied_rows = [row for row in claim_rows if "denied" in _claim_status(row).lower()]
    pending_rows = [row for row in claim_rows if "pending" in _claim_status(row).lower()]

    if any(keyword in lowered for keyword in ("denied", "denial", "appeal", "failed")):
        return denied_rows, "denied claims"
    if "pending" in lowered:
        return pending_rows, "pending claims"
    if any(keyword in lowered for keyword in ("open", "unsubmitted", "follow-up", "follow up", "status update", "outstanding", "problem", "workflow", "action")):
        return open_rows, "open or follow-up claims"
    if any(keyword in lowered for keyword in ("documentation", "attachment", "narrative", "supporting")):
        return open_rows, "claims needing documentation review"
    if any(keyword in lowered for keyword in ("payer", "exposure", "total", "highest")):
        return claim_rows, "claims by payer or exposure"
    if any(keyword in lowered for keyword in ("procedure", "bundle", "mismatch")):
        return open_rows, "procedure-related open claims"
    if "balance" in lowered:
        return open_rows or claim_rows, "claim balances"
    if "paid" in lowered:
        return [row for row in claim_rows if _claim_status(row).lower() == "paid"], "paid claims"
    return open_rows or claim_rows, "claims in approved export"


def _build_claim_total_answer(rows: list[dict[str, object]]) -> str:
    totals: dict[str, float] = {}
    for row in rows:
        payer = _claim_field(row, "Payer") or "unknown payer"
        totals[payer] = totals.get(payer, 0.0) + _claim_amount(row)
    if not totals:
        return "The approved SoftDent claims export does not contain payer totals for this question."
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return "Payer exposure from the approved SoftDent claims export: " + "; ".join(f"{payer} {_format_currency(amount)}" for payer, amount in ranked) + "."


def _should_suggest_governed_memory(question: str) -> bool:
    lowered = question.lower()
    return any(phrase in lowered for phrase in STABLE_MEMORY_REQUEST_PHRASES)


def _append_governed_memory_proposal(answer: str, *, question: str) -> str:
    if not _should_suggest_governed_memory(question):
        return answer
    if GOVERNED_MEMORY_PROPOSAL_PHRASE in answer:
        return answer
    return f"{answer.rstrip()} {GOVERNED_MEMORY_PROPOSAL_PHRASE}"


def _format_staff_assistant_answer(
    *,
    practical: str,
    reason: str | None = None,
    next_action: str | None = None,
    missing_data: str | None = None,
) -> str:
    parts = [practical.strip()]
    if reason:
        parts.append(f"Reason: {reason.strip()}")
    if next_action:
        parts.append(f"Next action: {next_action.strip()}")
    if missing_data:
        parts.append(f"Missing data: {missing_data.strip()}")
    return " ".join(parts)


def _is_patient_ar_balance_question(question: str) -> bool:
    lowered = question.lower()
    return "patient" in lowered and any(
        keyword in lowered
        for keyword in ("a/r", "accounts receivable", "balance owed", "outstanding balance", "patient balance", "patient ar")
    )


def _patient_level_softdent_ar_export_available() -> bool:
    rows = load_softdent_ar_rows()
    if not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if any(str(row.get(key) or "").strip() for key in ("PatientName", "patient_name", "MRN", "mrn", "patient_id")):
            return True
    return False


def _build_missing_patient_ar_answer(patient_name: str) -> str:
    return _format_staff_assistant_answer(
        practical=f"Patient A/R for {patient_name} is unavailable from the approved SoftDent exports.",
        reason="missing_softdent_ar: no patient-level SoftDent A/R export is present, so balances must not be reported as $0 or inferred from claim totals.",
        next_action="Import or refresh the SoftDent patient A/R export, then ask again for the balance.",
        missing_data="SoftDent patient A/R export",
    )


def _build_multiple_open_patient_answer(rows: list[dict[str, object]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        patient = _claim_field(row, "PatientName") or "unknown patient"
        counts[patient] = counts.get(patient, 0) + 1
    patients = [f"{patient} ({count} open claims)" for patient, count in counts.items() if count > 1]
    if patients:
        return _format_staff_assistant_answer(
            practical="Patients with multiple open claims in the approved SoftDent export: " + "; ".join(patients) + ".",
            reason="Counts come from open claim rows in the local SoftDent export.",
            next_action="I would prioritize follow-up on the highest-dollar open claims first.",
        )
    return _format_staff_assistant_answer(
        practical="The approved SoftDent claims export does not verify any patient with multiple open claims.",
        reason="No patient had more than one open claim row in the reviewed export.",
        missing_data="Confirm the claims export is current if you expected multiple open claims.",
    )


def _build_immediate_patient_claims_second_opinion(context_bundle: dict[str, object]) -> tuple[str, dict[str, object]]:
    question = str(context_bundle.get("sanitized_question") or "")
    raw_claim_rows = context_bundle.get("claim_rows")
    claim_rows = raw_claim_rows if isinstance(raw_claim_rows, list) else []
    audit_meta: dict[str, object] = {
        "label": "",
        "selected_rows": [],
    }
    if not claim_rows:
        return (
            _format_staff_assistant_answer(
                practical="I do not have readable claim rows in the approved SoftDent export for this second opinion.",
                reason="The local claims export was checked but returned no usable rows.",
                missing_data="Please confirm the SoftDent claims export is current or name the claim you want reviewed.",
            ),
            audit_meta,
        )

    lowered = question.lower()
    selected_rows, label = _claim_rows_for_question(question, claim_rows)
    audit_meta["label"] = label
    audit_meta["selected_rows"] = selected_rows[:3]
    if "multiple open" in lowered or ("multiple" in lowered and "open" in lowered):
        answer = _build_multiple_open_patient_answer([row for row in claim_rows if _is_open_claim(row)])
        return answer, audit_meta
    if any(keyword in lowered for keyword in ("total", "highest", "exposure")):
        return _build_claim_total_answer(selected_rows), audit_meta
    if "mismatch" in lowered:
        if selected_rows:
            practical = (
                "The approved SoftDent claims export does not contain a verified mismatch field. "
                f"Open procedure-related claims available for review: {' | '.join(_format_claim_row(row) for row in selected_rows[:3])}."
            )
        else:
            practical = "The approved SoftDent claims export does not verify procedure mismatches or open procedure claims for this question."
        answer = _format_staff_assistant_answer(
            practical=practical,
            reason="Mismatch checks require explicit fields or documentation not present in the export row shape.",
            next_action="Compare the chart note, procedure code, and payer response before preparing an appeal packet.",
        )
        return answer, audit_meta
    if not selected_rows:
        return (
            _format_staff_assistant_answer(
                practical=f"The approved SoftDent claims export does not verify any {label} for this question.",
                reason="No matching claim rows were found in the local export for the filters implied by the question.",
                missing_data="Provide a patient name, claim ID, or payer if you want a narrower review.",
            ),
            audit_meta,
        )

    formatted_rows = [_format_claim_row(row) for row in selected_rows[:3]]
    answer = _format_staff_assistant_answer(
        practical=f"Verified {label} from the approved SoftDent export: " + " | ".join(formatted_rows) + ".",
        reason="These rows come from the approved local SoftDent claims export reviewed for this question.",
        next_action="I would review payer status, missing documentation, and whether an appeal or resubmission packet is needed before anything is sent.",
    )
    return answer, audit_meta


def _build_second_opinion_audit_summary(
    answer: str,
    *,
    deterministic_claims_fast_path: bool,
    claims_audit_meta: dict[str, object] | None,
) -> str:
    del deterministic_claims_fast_path, claims_audit_meta
    cleaned = " ".join(answer.split())
    if "PatientName,MRN,ClaimId" in cleaned:
        cleaned = cleaned.replace("PatientName,MRN,ClaimId", "[csv header redacted]")
    return cleaned[:180]


def _is_quickbooks_write_request(question: str) -> bool:
    lowered = question.lower()
    return "quickbooks" in lowered and any(keyword in lowered for keyword in ("post", "apply", "send", "update", "change"))


def _is_collections_follow_up_request(question: str) -> bool:
    lowered = question.lower()
    return ("collections" in lowered or "gap" in lowered or "shortfall" in lowered) and any(keyword in lowered for keyword in ("what should i do", "before lunch", "next"))


def _is_weakest_provider_request(question: str) -> bool:
    lowered = question.lower()
    return "provider" in lowered and any(keyword in lowered for keyword in ("weakest", "lowest", "worst"))


def _is_action_summary_request(question: str) -> bool:
    lowered = question.lower()
    return "top two action items" in lowered or ("summarize" in lowered and "without inventing anything new" in lowered)


def _is_ar_availability_question(question: str) -> bool:
    lowered = question.lower()
    if not any(keyword in lowered for keyword in ("a/r", " ar ", "accounts receivable", "receivable", "daysheet")):
        return False
    return any(
        keyword in lowered
        for keyword in (
            "available",
            "availability",
            "imported",
            "status",
            "missing",
            "ready",
            "can i use",
            "is there",
        )
    )


def _is_missing_exports_question(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "which exports are missing",
            "what exports are missing",
            "missing exports",
            "exports missing",
            "which sources are missing",
            "what sources are missing",
            "missing source",
            "missing data sources",
        )
    )


def _is_claim_packet_readiness_question(question: str) -> bool:
    lowered = question.lower()
    if "claim packet readiness" in lowered:
        return True
    if "packet readiness" in lowered and "claim" in lowered:
        return True
    if "which claim packets are blocked" in lowered:
        return True
    if "what claims need documents" in lowered:
        return True
    if "claims need documents" in lowered:
        return True
    if "what can hal draft locally" in lowered and any(
        token in lowered for token in ("claim", "packet", "narrative", "denial")
    ):
        return True
    return any(
        phrase in lowered
        for phrase in (
            "is this claim packet ready",
            "claim packet ready",
            "blocked claim packets",
            "claims blocked for documents",
        )
    )


def _is_complex_hal_question(question: str, context_bundle: dict[str, object]) -> bool:
    patient_context = context_bundle.get("patient_context")
    if isinstance(patient_context, dict) and bool(patient_context.get("matched")):
        return True
    lowered = question.lower()
    complex_keywords = (
        "narrative",
        "appeal",
        "denial",
        "denied claim",
        "clinical note",
        "patient dossier",
        "packet review",
        "conflict",
        "contradict",
        "legal",
        "vendor contract",
        "insurance letter",
        "writeback",
        "resubmit",
    )
    if any(keyword in lowered for keyword in complex_keywords):
        return True
    if _is_patient_follow_up_question(question):
        return True
    if _is_patient_ar_balance_question(question):
        return True
    return False


def _is_routine_office_question(question: str, context_bundle: dict[str, object]) -> bool:
    if _is_complex_hal_question(question, context_bundle):
        return False
    if _is_generic_help_request(question):
        return False
    if _is_ar_availability_question(question) or _is_missing_exports_question(question):
        return False
    if _is_claim_packet_readiness_question(question):
        return False
    lowered = question.lower()
    routine_patterns = (
        "what needs attention",
        "needs attention today",
        "summarize today",
        "today's tasks",
        "todays tasks",
        "morning huddle",
        "prepare morning huddle",
        "explain this status",
        "explain the status",
        "short summary",
        "office summary",
        "staff focus",
        "focus on today",
        "what should staff",
    )
    return any(pattern in lowered for pattern in routine_patterns)


def _is_operational_prompt(question: str, context_bundle: dict[str, object]) -> bool:
    return (
        _is_routine_office_question(question, context_bundle)
        or _is_complex_hal_question(question, context_bundle)
        or _is_ar_availability_question(question)
        or _is_missing_exports_question(question)
        or _is_patient_follow_up_question(question)
        or _is_patient_ar_balance_question(question)
    )


def _context_has_real_office_facts(context_bundle: dict[str, object]) -> bool:
    patient_context = context_bundle.get("patient_context")
    if isinstance(patient_context, dict) and bool(patient_context.get("matched")):
        return True

    state = context_bundle.get("state")
    if isinstance(state, dict):
        action_items = [str(item).strip() for item in state.get("action_items", []) if str(item).strip()]
        if action_items:
            return True

    for key in ("softdent_aggregate_context", "live_report_context", "combined_context"):
        items = context_bundle.get(key)
        if not isinstance(items, list):
            continue
        if any(isinstance(item, dict) and _is_verified_operational_context_item(item) for item in items):
            return True
    return False


def _context_is_documentation_or_diagnostic_only(context_bundle: dict[str, object]) -> bool:
    items = context_bundle.get("combined_context")
    if not isinstance(items, list) or not items:
        return False
    dict_items = [item for item in items if isinstance(item, dict)]
    if not dict_items:
        return False
    if _context_has_real_office_facts(context_bundle):
        return False
    return all(_is_documentation_context_item(item) or _is_source_health_diagnostic_context_item(item) for item in dict_items)


def _is_claim_or_narrative_prompt(question: str) -> bool:
    lowered = question.lower()
    return any(
        keyword in lowered
        for keyword in (
            "claim",
            "denial",
            "denied",
            "appeal",
            "narrative",
            "payer",
            "clinical note",
        )
    )


def _should_allow_deterministic_short_circuit(
    *,
    question: str,
    context_bundle: dict[str, object],
    answer: str,
    patient_matched: bool,
) -> bool:
    if not _deterministic_answer_is_substantive(answer, patient_matched=patient_matched):
        return False

    # These paths are authoritative server facts or safety boundaries and should
    # remain deterministic even without model routing.
    if (
        _is_generic_help_request(question)
        or _is_ar_availability_question(question)
        or _is_missing_exports_question(question)
        or _is_claim_packet_readiness_question(question)
        or _is_quickbooks_write_request(question)
        or _is_action_summary_request(question)
    ):
        return True

    if patient_matched:
        return True

    if _is_complex_hal_question(question, context_bundle):
        # Claim/narrative reasoning should reach the primary HAL model unless a
        # patient-specific deterministic path already matched above.
        return False

    if _is_routine_office_question(question, context_bundle):
        # Routine operational prompts should not be satisfied by docs/source
        # prose. They either use the fast model with real facts or the clean
        # no-context checklist.
        return False

    if _is_operational_prompt(question, context_bundle):
        return _context_has_real_office_facts(context_bundle)

    return True


def _deterministic_status_cache_ttl_seconds() -> float:
    try:
        return max(float(os.getenv("HAL_DETERMINISTIC_STATUS_CACHE_SECONDS", "30")), 0.0)
    except ValueError:
        return 30.0


def _get_cached_deterministic_response(cache_key: str) -> dict[str, object] | None:
    ttl = _deterministic_status_cache_ttl_seconds()
    if ttl <= 0:
        return None
    with _deterministic_status_cache_lock:
        cached = _deterministic_status_cache.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= time.monotonic():
            _deterministic_status_cache.pop(cache_key, None)
            return None
        return dict(payload)


def _store_cached_deterministic_response(cache_key: str, payload: dict[str, object]) -> None:
    ttl = _deterministic_status_cache_ttl_seconds()
    if ttl <= 0:
        return
    with _deterministic_status_cache_lock:
        _deterministic_status_cache[cache_key] = (time.monotonic() + ttl, dict(payload))


def _attach_routing_metadata(
    payload: dict[str, object],
    *,
    answer_lane: str,
    model_used: str | None = None,
    escalated: bool = False,
    routing_elapsed_ms: int | None = None,
) -> dict[str, object]:
    enriched = dict(payload)
    enriched["answer_lane"] = answer_lane
    enriched["model_used"] = model_used
    enriched["escalated"] = escalated
    if routing_elapsed_ms is not None:
        enriched["routing_elapsed_ms"] = routing_elapsed_ms
    return enriched


def _log_hal_routing(
    *,
    question: str,
    answer_lane: str,
    model_used: str | None,
    escalated: bool,
    routing_elapsed_ms: int,
    model_called: bool,
) -> None:
    category = "complex" if _is_complex_hal_question(question, {"patient_context": {"matched": False}}) else "routine"
    if _is_generic_help_request(question):
        category = "generic_help"
    elif _is_ar_availability_question(question) or _is_missing_exports_question(question) or _is_claim_packet_readiness_question(question):
        category = "source_status"
    logger.info(
        "HAL ask routing category=%s lane=%s model=%s elapsed_ms=%s model_called=%s escalated=%s",
        category,
        answer_lane,
        model_used or "none",
        routing_elapsed_ms,
        model_called,
        escalated,
    )


def _build_ar_import_next_steps() -> str:
    return (
        "What to do next:\n"
        "- Export the latest SoftDent Daily End-of-Day / DAYSHEET report.\n"
        "- Place it in the local daily_end_of_day import folder.\n"
        "- Refresh HAL.\n"
        "Missing A/R is unavailable, not $0."
    )


def _build_ar_availability_status_answer() -> str:
    from app.services import get_softdent_end_of_day_ar_source_status

    status = get_softdent_end_of_day_ar_source_status()
    parse_status = str(status.get("parse_status") or "missing")
    if bool(status.get("available")) and parse_status in {"available", "limited"}:
        report_date = str(status.get("report_date") or "").strip()
        if report_date:
            return (
                f"SoftDent DAYSHEET A/R is available from the imported report dated {report_date}. "
                "Use Check today's A/R for the verified balance."
            )
        return "SoftDent DAYSHEET A/R is available from an imported daily end-of-day report."
    if parse_status == "stale":
        return (
            "SoftDent DAYSHEET A/R report is present but stale.\n"
            "A/R balances are unavailable until a current SoftDent Daily End-of-Day / DAYSHEET report is imported.\n"
            f"{_build_ar_import_next_steps()}"
        )
    return (
        "SoftDent DAYSHEET A/R is not imported yet.\n"
        "A/R balances are unavailable until a current SoftDent Daily End-of-Day / DAYSHEET report is imported.\n"
        f"{_build_ar_import_next_steps()}"
    )


def _build_missing_exports_status_answer() -> str:
    from app.services import get_softdent_data_coverage

    coverage = get_softdent_data_coverage()
    rows = coverage.get("rows") if isinstance(coverage.get("rows"), list) else []
    missing_labels: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").lower() == "available":
            continue
        label = str(row.get("label") or "").strip()
        if label:
            missing_labels.append(label)
    if not missing_labels:
        return "All tracked SoftDent exports are currently available from the approved local import lane."
    joined = ", ".join(missing_labels[:6])
    suffix = " Re-import the missing exports before relying on those workflows." if missing_labels else ""
    return f"Missing or unavailable SoftDent exports: {joined}.{suffix}"


def _build_claim_packet_readiness_status_answer(*, actor: str) -> str:
    from app.hal.claim_packet_readiness import build_claim_packet_readiness_answer

    return build_claim_packet_readiness_answer(actor=actor)


def _is_operating_picture_request(question: str) -> bool:
    lowered = question.lower()
    return "operating picture" in lowered or "what can you do" in lowered or "capabilities" in lowered or (
        "hal" in lowered and any(keyword in lowered for keyword in ("status", "runtime", "health", "model", "routing"))
    )


def _needs_operating_picture_for_question(question: str) -> bool:
    return _is_operating_picture_request(question) and not _is_follow_up_question(question)


def _deterministic_answer_is_substantive(answer: str, *, patient_matched: bool) -> bool:
    if patient_matched:
        return True
    normalized = answer.strip()
    if not normalized:
        return False
    generic_fallback = (
        "I can review approved local office context for a specific patient, claim, metric, or task."
    )
    if normalized.startswith(generic_fallback) and len(normalized) < 240:
        return False
    return True


def _build_quickbooks_write_boundary_answer() -> str:
    return (
        "I cannot post that in QuickBooks myself. "
        "The next safe step is to review the adjustment draft, validate the journal lines, and prepare the posting package for human review."
    )


def _build_collections_follow_up_answer(softdent_items: list[dict[str, str]]) -> str:
    delta_item = next((item for item in softdent_items if str(item.get("source_id") or "") == "softdent-live-collection-delta"), None)
    delta = _format_currency(delta_item.get("collection_delta")) if delta_item else "$0.00"
    ratio = str(delta_item.get("collection_ratio") or "0.00") if delta_item else "0.00"
    return (
        f"First, review the A/R aging and outstanding balances behind the current {delta} collections gap. "
        f"That will show whether the {ratio}% collection ratio is being driven by insurer lag, unpaid patient balances, or claim backlog."
    )


def _build_weakest_provider_answer(softdent_items: list[dict[str, str]]) -> str:
    ranking_item = next((item for item in softdent_items if str(item.get("source_id") or "") == "softdent-live-provider-ranking"), None)
    if ranking_item is None:
        return "The current provider ranking context is not available."
    weakest_name = str(ranking_item.get("weakest_provider_name") or "Unknown")
    weakest_production = _format_currency(ranking_item.get("weakest_provider_production"))
    weakest_collections = _format_currency(ranking_item.get("weakest_provider_collections"))
    return (
        f"The weakest provider in the current SoftDent snapshot is {weakest_name}. "
        f"They are trailing at {weakest_production} in production and {weakest_collections} in collections relative to the other providers in this snapshot."
    )


def _should_use_concise_answer_frame(question: str) -> bool:
    return any(
        (
            _is_quickbooks_write_request(question),
            _is_collections_follow_up_request(question),
            _is_weakest_provider_request(question),
            _is_action_summary_request(question),
            _is_generic_help_request(question),
        )
    )


def _normalize_help_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower()).strip("?!.")


def _is_generic_help_request(question: str) -> bool:
    normalized = _normalize_help_question(question)
    if not normalized:
        return False
    if normalized in {"help", "hal help", "help hal", "help me", "help please", "i need help"}:
        return True
    generic_prefixes = (
        "can you help",
        "could you help",
        "what can you do",
        "what can hal help",
        "what can hal do",
        "how can you help",
        "how can hal help",
        "how can you help the office",
        "what do you do",
    )
    return any(normalized.startswith(prefix) for prefix in generic_prefixes)


def _user_asked_for_sources(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "what sources",
            "which sources",
            "where did you get",
            "what did you look at",
            "show sources",
            "what sources did you use",
        )
    )


def _friendly_source_label(title: str) -> str:
    normalized = title.strip()
    if re.fullmatch(r"(?i)readme chunk \d+", normalized):
        return "README guidance"
    if re.search(r"(?i)\bchunk \d+\b", normalized):
        return "approved local office context"
    return normalized


def _summarize_sources_for_display(items: list[dict[str, object]]) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for item in items:
        label = _friendly_source_label(_get_context_title(item))
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return ", ".join(labels)


def _dedupe_answer_parts(parts: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return " ".join(ordered)


def _build_generic_help_answer_text() -> str:
    return (
        "Yes. I can help with local office tasks, claim follow-up drafts, patient prep summaries, "
        "report checklists, SoftDent export review, and internal office-manager summaries. "
        "I stay local and read-only. I can prepare drafts and packets for review, but I do not submit claims, "
        "contact payers, email, fax, upload, use Gateway/E-Services, or write back to SoftDent."
    )


def _build_generic_help_hal_response(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    sanitized: dict[str, object],
) -> dict[str, object]:
    sanitized_question = str(sanitized.get("sanitized_text") or "")
    answer = _build_generic_help_answer_text()
    state = _get_conversation_state(actor, session_id)
    _update_conversation_state(
        actor=actor,
        session_id=session_id,
        state=state,
        question=question,
        patient_context={"matched": False},
        softdent_aggregate_context=[],
        hardware_review_actions=[],
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="hal-generic-help",
        detail=f"Answered a generic HAL help request for sanitized request: {sanitized_question[:140]}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:generic-help",
        sanitized_question=sanitized_question,
        retrieval_ids=[],
        response_summary=answer[:180],
    )
    return {
        "mode": f"{HAL_MODE}:generic-help",
        "answer": answer,
        "sanitized_question": sanitized_question,
        "sanitization_findings": sanitized.get("findings", []),
        "retrieved_context": [],
        "guardrails": [
            "approved local read-only scope",
            "deterministic generic help response",
            "read-only data boundary",
            "audit log recorded",
            "hardware mutations require human confirmation",
            "tier-1 critical actions require explicit confirmation",
        ],
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "review_actions": [],
        "voice_profile": _voice_profile("primary"),
        "governance_notes": _build_governance_notes(),
    }


def _build_patient_follow_up_plan(patient_context: dict[str, object]) -> str:
    summary_fields = patient_context.get("summary_fields") if isinstance(patient_context.get("summary_fields"), dict) else {}
    patient_name = str(summary_fields.get("patient_name") or "the patient")
    primary_status = str(summary_fields.get("primary_claim_status") or "under review")
    total_claim_amount = _format_currency(summary_fields.get("total_claim_amount"))
    return (
        f"For {patient_name} today, start by reviewing the {primary_status.lower()} claim support tied to the {total_claim_amount} balance. "
        "Then package the clinical documentation and payer-facing narrative for resubmission or appeal, and record the next follow-up checkpoint in the local review trail."
    )


def _build_action_summary_answer(action_items: list[str]) -> str:
    selected = [item for item in action_items if item][:2]
    if not selected:
        return "No verified action items were captured from the recent conversation."
    if len(selected) == 1:
        return f"Top action item: {selected[0]}"
    return f"Top two action items: 1. {selected[0]} 2. {selected[1]}"


def _update_conversation_state(
    *,
    actor: str,
    session_id: str | None,
    state: dict[str, object],
    question: str,
    patient_context: dict[str, object],
    softdent_aggregate_context: list[dict[str, str]],
    hardware_review_actions: list[dict[str, object]],
) -> None:
    updated_state = dict(state)
    action_items = [str(item) for item in updated_state.get("action_items", []) if str(item).strip()]
    summary_fields = patient_context.get("summary_fields") if isinstance(patient_context.get("summary_fields"), dict) else {}
    patient_name = str(summary_fields.get("patient_name") or "").strip()
    if patient_name:
        updated_state["last_patient_name"] = patient_name
    if any(str(item.get("source_id") or "") == "softdent-live-collection-delta" for item in softdent_aggregate_context):
        delta_item = next(item for item in softdent_aggregate_context if str(item.get("source_id") or "") == "softdent-live-collection-delta")
        delta = _format_currency(delta_item.get("collection_delta"))
        action = f"Review the A/R aging and outstanding balances behind the current {delta} collections gap."
        if action not in action_items:
            action_items.append(action)
    elif any(str(item.get("source_id") or "") == "softdent-live-summary" for item in softdent_aggregate_context):
        summary_item = next(item for item in softdent_aggregate_context if str(item.get("source_id") or "") == "softdent-live-summary")
        production = float(summary_item.get("total_production") or 0.0)
        collections = float(summary_item.get("total_collections") or 0.0)
        delta = _format_currency(round(production - collections, 2))
        action = f"Review the A/R aging and outstanding balances behind the current {delta} collections gap."
        if action not in action_items:
            action_items.append(action)
    if patient_name and str(summary_fields.get("primary_claim_status") or "").lower() == "denied":
        action = f"Review {patient_name}'s denied claim support and prepare the resubmission or appeal package."
        if action not in action_items:
            action_items.append(action)
    if hardware_review_actions:
        action = str(hardware_review_actions[0].get("title") or "").strip()
        if action and action not in action_items:
            action_items.append(action)
    updated_state["action_items"] = action_items[-6:]
    updated_state["last_question"] = question
    _save_conversation_state(actor, session_id, updated_state)


def _extract_report_period(question: str) -> ReportPeriod:
    lowered = question.lower()

    if "last month" in lowered:
        today = datetime.now(timezone.utc)
        first_this_month = today.replace(day=1)
        last_day_previous_month = first_this_month - timedelta(days=1)
        return ReportPeriod(
            start_date=last_day_previous_month.replace(day=1).strftime("%Y-%m-%d"),
            end_date=last_day_previous_month.strftime("%Y-%m-%d"),
        )

    if "this quarter" in lowered:
        today = datetime.now(timezone.utc)
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        return ReportPeriod(
            start_date=today.replace(month=quarter_start_month, day=1).strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
        )

    if "this month" in lowered:
        today = datetime.now(timezone.utc)
        return ReportPeriod(
            start_date=today.replace(day=1).strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
        )

    matched_dates = REPORT_DATE_PATTERN.findall(question)
    if len(matched_dates) >= 2:
        return ReportPeriod(start_date=matched_dates[0], end_date=matched_dates[1])

    if len(matched_dates) == 1:
        end_date = datetime.strptime(matched_dates[0], "%Y-%m-%d")
        return ReportPeriod(
            start_date=end_date.replace(day=1).strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )

    today = datetime.now(timezone.utc)
    return ReportPeriod(
        start_date=today.replace(day=1).strftime("%Y-%m-%d"),
        end_date=today.strftime("%Y-%m-%d"),
    )


def _make_report_context_snippet(*, source_id: str, title: str, excerpt: str) -> dict[str, str]:
    sanitized = sanitize_hal_text(excerpt)
    return {
        "source_id": source_id,
        "title": title,
        "category": "quickbooks_tool",
        "excerpt": str(sanitized["sanitized_text"]),
    }


def _make_softdent_context_snippet(*, source_id: str, title: str, excerpt: str) -> dict[str, str]:
    sanitized = sanitize_hal_text(excerpt)
    return {
        "source_id": source_id,
        "title": title,
        "category": "softdent_aggregate",
        "excerpt": str(sanitized["sanitized_text"]),
    }


def _build_report_excerpt(*, label: str, period: ReportPeriod, payload: dict[str, object]) -> str:
    summary_fields = payload.get("summary_fields") if isinstance(payload.get("summary_fields"), dict) else {}
    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
    source_backend = str(payload.get("source_backend") or "empty")
    metric_parts: list[str] = []

    if "total_revenue" in summary_fields:
        metric_parts.append(f"total revenue {_format_currency(summary_fields.get('total_revenue'))}")
    if "total_expense" in summary_fields:
        metric_parts.append(f"total expense {_format_currency(summary_fields.get('total_expense'))}")
    if "net_income" in summary_fields:
        metric_parts.append(f"net income {_format_currency(summary_fields.get('net_income'))}")
    if "total_outstanding_ar" in summary_fields:
        metric_parts.append(f"total outstanding A/R {_format_currency(summary_fields.get('total_outstanding_ar'))}")
    if "row_count" in summary_fields:
        metric_parts.append(f"row count {summary_fields.get('row_count')}")

    period_bound = bool(health.get("period_bound"))
    data_complete = bool(health.get("data_complete"))
    warning = str(health.get("warning") or "").strip()
    error = str(health.get("error") or "").strip()
    metric_text = "; ".join(metric_parts) if metric_parts else "no calculated metrics available"
    detail_parts = [
        f"QuickBooks verified {label} report for {period.start_date} to {period.end_date}",
        f"source backend {source_backend}",
        metric_text,
        f"data complete {data_complete}",
        f"period bound {period_bound}",
    ]
    if warning:
        detail_parts.append(f"warning {warning}")
    if error:
        detail_parts.append(f"error {error}")
    return ". ".join(detail_parts) + "."


def _format_currency(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    return f"${amount:,.2f}"


def _build_softdent_snapshot_excerpt(payload: dict[str, object]) -> str:
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    production = _format_currency(totals.get("production"))
    collections = _format_currency(totals.get("collections"))
    insurance = _format_currency(totals.get("insurance"))
    patient = _format_currency(totals.get("patient"))
    return (
        f"Verified SoftDent practice snapshot for {payload.get('period_start') or 'unknown'} to {payload.get('period_end') or 'unknown'}. "
        f"Providers tracking {int(payload.get('provider_count') or 0)}. "
        f"Total production {production}. Total collections {collections}. Total insurance {insurance}. Total patient {patient}. "
        f"Data complete {bool(payload.get('data_complete'))}."
    )


def compile_softdent_aggregate_snippets(question: str) -> list[dict[str, str]]:
    lowered = question.lower()
    wants_provider_ranking = any(keyword in lowered for keyword in ("provider", "ranking", "rank", "doctor", "hygienist", "performer", "production by provider"))
    wants_payer_mix = any(keyword in lowered for keyword in ("payer mix", "mix", "insurance share", "patient share", "insurance mix", "patient mix"))
    wants_collection_delta = any(keyword in lowered for keyword in ("delta", "gap", "shortfall", "collections gap", "production delta", "collection ratio"))
    wants_summary = any(keyword in lowered for keyword in ("softdent", "production", "collections", "insurance", "patient", "practice collections")) and not (
        wants_provider_ranking or wants_payer_mix or wants_collection_delta
    )

    snippets: list[dict[str, str]] = []
    aggregate_payload = fetch_softdent_dashboard_aggregate() if (wants_summary or wants_provider_ranking or wants_payer_mix or wants_collection_delta) else {}
    aggregate_totals = aggregate_payload.get("totals") if isinstance(aggregate_payload.get("totals"), dict) else {}
    aggregate_rows = aggregate_payload.get("provider_rows") if isinstance(aggregate_payload.get("provider_rows"), list) else []

    if wants_summary:
        payload = aggregate_payload
        if bool(aggregate_rows):
            period_start = str(payload.get("period_start") or "")
            period_end = str(payload.get("period_end") or "")
            totals = aggregate_totals
            production_total = float(totals.get("production") or 0.0)
            collections_total = float(totals.get("collections") or 0.0)
            collection_ratio = round((collections_total / production_total) * 100, 2) if production_total else 0.0
            snippets.append(
                {
                    **_make_softdent_context_snippet(
                    source_id="softdent-live-summary",
                    title=f"Verified SoftDent practice performance snapshot ({period_start} to {period_end})",
                    excerpt=_build_softdent_snapshot_excerpt(payload),
                    ),
                    "total_production": f"{production_total}",
                    "total_collections": f"{collections_total}",
                    "collection_ratio": f"{collection_ratio:.2f}",
                }
            )

    if wants_provider_ranking:
        provider_status = get_softdent_provider_ranking_status()
        provider_excerpt = str(provider_status.get("excerpt") or "The current provider ranking context is not available.")
        top_provider = aggregate_rows[0] if aggregate_rows else {}
        weakest_provider = aggregate_rows[0] if aggregate_rows else {}
        if aggregate_rows:
            top_provider = max(aggregate_rows, key=lambda row: float(row.get("production_amount") or 0.0))
            weakest_provider = min(aggregate_rows, key=lambda row: float(row.get("production_amount") or 0.0))
        snippets.append(
            {
                **_make_softdent_context_snippet(
                    source_id="softdent-live-provider-ranking",
                    title="SoftDent live provider ranking",
                    excerpt=provider_excerpt,
                ),
                "top_provider_name": str(top_provider.get("provider_name") or ""),
                "top_provider_production": f"{float(top_provider.get('production_amount') or 0.0)}",
                "weakest_provider_name": str(weakest_provider.get("provider_name") or ""),
                "weakest_provider_production": f"{float(weakest_provider.get('production_amount') or 0.0)}",
                "weakest_provider_collections": f"{float(weakest_provider.get('collection_amount') or weakest_provider.get('collections_amount') or weakest_provider.get('collections') or 0.0)}",
            }
        )

    if wants_payer_mix:
        payer_mix_status = get_softdent_payer_mix_status()
        payer_mix_excerpt = str(payer_mix_status.get("excerpt") or "The current payer mix context is not available.")
        insurance_total = float(aggregate_totals.get("insurance") or 0.0)
        patient_total = float(aggregate_totals.get("patient") or 0.0)
        collections_total = float(aggregate_totals.get("collections") or 0.0)
        insurance_share = round((insurance_total / collections_total) * 100, 2) if collections_total else 0.0
        patient_share = round((patient_total / collections_total) * 100, 2) if collections_total else 0.0
        snippets.append(
            {
                **_make_softdent_context_snippet(
                    source_id="softdent-live-payer-mix",
                    title="SoftDent live payer mix",
                    excerpt=payer_mix_excerpt,
                ),
                "insurance_total": f"{insurance_total}",
                "patient_total": f"{patient_total}",
                "insurance_share": f"{insurance_share:.2f}",
                "patient_share": f"{patient_share:.2f}",
            }
        )

    if wants_collection_delta:
        collection_delta_status = get_softdent_collection_delta_status()
        collection_delta_excerpt = str(collection_delta_status.get("excerpt") or "The current collections delta context is not available.")
        production_total = float(aggregate_totals.get("production") or 0.0)
        collections_total = float(aggregate_totals.get("collections") or 0.0)
        collection_delta = round(production_total - collections_total, 2)
        collection_ratio = round((collections_total / production_total) * 100, 2) if production_total else 0.0
        snippets.append(
            {
                **_make_softdent_context_snippet(
                    source_id="softdent-live-collection-delta",
                    title="SoftDent live collections delta",
                    excerpt=collection_delta_excerpt,
                ),
                "collection_delta": f"{collection_delta}",
                "collection_ratio": f"{collection_ratio:.2f}",
            }
        )

    return snippets


def compile_hardware_snippets(sanitized_question: str) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    lowered = sanitized_question.lower()
    has_display_query = any(
        keyword in lowered
        for keyword in ("brightness", "contrast", "monitor setting", "display input", "screen tint", "display status")
    )

    if not has_display_query:
        return snippets

    monitor_data = get_monitor_status()
    health = monitor_data.get("health") if isinstance(monitor_data.get("health"), dict) else {}
    if bool(health.get("connected")):
        raw_vcp_codes = monitor_data.get("raw_vcp_codes") if isinstance(monitor_data.get("raw_vcp_codes"), dict) else {}
        input_source_raw = raw_vcp_codes.get("input_source_raw")
        raw_code_clause = f" (Raw Code={input_source_raw})" if input_source_raw is not None else ""
        snippets.append(
            {
                "source_id": "physical_monitor_primary",
                "title": "Verified Physical Monitor Parameters (DDC/CI)",
                "category": "hardware_status",
                "excerpt": (
                    f"Panel: Brightness={monitor_data.get('brightness')}% | "
                    f"Contrast={monitor_data.get('contrast')}% | "
                    f"Active Input={monitor_data.get('input_source')}{raw_code_clause}."
                ),
                "brightness": monitor_data.get("brightness"),
                "contrast": monitor_data.get("contrast"),
                "input_source": monitor_data.get("input_source"),
                "raw_vcp_codes": raw_vcp_codes,
            }
        )
    else:
        snippets.append(
            {
                "source_id": "physical_monitor_offline",
                "title": "Physical Monitor State Unavailable",
                "category": "hardware_status",
                "excerpt": f"Status: Unconfigured/Unsupported. Error details: {health.get('error')}",
            }
        )

    return snippets


def compile_live_report_snippets(question: str) -> list[dict[str, str]]:
    lowered = question.lower()
    wants_profit_loss = any(term in lowered for term in ("p&l", "profit and loss", "profit & loss")) or (
        "quickbooks" in lowered and "revenue" in lowered and any(term in lowered for term in ("expense", "expenses", "net income"))
    )
    wants_balance_sheet = "balance sheet" in lowered or (
        "quickbooks" in lowered and "assets" in lowered and "liabilities" in lowered
    )
    wants_ar_aging = any(term in lowered for term in ("a/r aging", "ar aging", "accounts receivable aging", "receivables aging")) or (
        "quickbooks" in lowered and "outstanding balances" in lowered
    )

    if not (wants_profit_loss or wants_balance_sheet or wants_ar_aging):
        return []

    period = _extract_report_period(question)
    snippets: list[dict[str, str]] = []

    if wants_profit_loss:
        payload = get_profit_loss_report(period)
        snippets.append(
            _make_report_context_snippet(
                source_id=f"qb-pl-{period.start_date}-{period.end_date}",
                title=f"QuickBooks verified profit and loss {period.start_date} to {period.end_date}",
                excerpt=_build_report_excerpt(label="profit and loss", period=period, payload=payload),
            )
        )

    if wants_balance_sheet:
        payload = get_balance_sheet_report(period)
        snippets.append(
            _make_report_context_snippet(
                source_id=f"qb-balance-sheet-{period.end_date}",
                title=f"QuickBooks verified balance sheet as of {period.end_date}",
                excerpt=_build_report_excerpt(label="balance sheet", period=period, payload=payload),
            )
        )

    if wants_ar_aging:
        payload = get_ar_aging_report(period)
        snippets.append(
            _make_report_context_snippet(
                source_id=f"qb-ar-aging-{period.end_date}",
                title=f"QuickBooks verified A/R aging as of {period.end_date}",
                excerpt=_build_report_excerpt(label="accounts receivable aging", period=period, payload=payload),
            )
        )

    return snippets


_STAFF_ANSWER_ARTIFACT_SUBSTRINGS = (
    "No additional verified context retrieved.",
    "No additional verified context retrieved",
    "Use the answer above as the current staff recommendation.",
    "No follow-up question is required yet.",
)
_STAFF_ANSWER_ARTIFACT_LINE_PATTERN = re.compile(
    r"(?im)^\s*(?:we are given|according to the instructions|verified local context)\b[:\-]?.*$"
)
_STAFF_ANSWER_INLINE_ECHO_PATTERN = re.compile(
    r"(?i)\b(?:we are given|according to the instructions|verified local context)\b[:\-]?\s*\"?"
)


def _sanitize_staff_facing_answer(answer: str) -> str:
    """Remove leaked model/prompt template artifacts from a staff-facing answer.

    This strips internal prompt echoes (for example ``We are given:`` or
    ``Verified local context: No additional verified context retrieved.``) so the
    main HAL answer reads like a practical office manager. Real missing-data
    warnings are produced elsewhere in plain English and are not removed here.
    """
    if not answer:
        return answer
    text = answer
    for substring in _STAFF_ANSWER_ARTIFACT_SUBSTRINGS:
        text = text.replace(substring, "")
    text = _STAFF_ANSWER_ARTIFACT_LINE_PATTERN.sub("", text)
    text = _STAFF_ANSWER_INLINE_ECHO_PATTERN.sub("", text)
    text = re.sub(r'""', "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _build_routine_no_context_answer_text() -> str:
    return (
        "I do not have a verified office snapshot yet.\n"
        "What I can check next:\n"
        "- DAYSHEET / A/R import status\n"
        "- blocked claims\n"
        "- missing SoftDent exports\n"
        "- drafts waiting for review\n"
        "- local office tasks\n"
        "No patient-specific action should be taken until verified data is loaded."
    )


def _build_missing_claim_facts_answer_text() -> str:
    return (
        "I do not have verified claim facts for that narrative yet.\n"
        "What I need before drafting or reasoning through it:\n"
        "- the claim status and payer\n"
        "- denial reason or EOB notes\n"
        "- procedure and date of service\n"
        "- supporting clinical notes or attachments\n"
        "I can help organize a local draft once those facts are imported or provided for human review. "
        "I do not submit, email, fax, upload, contact payers, or write back to SoftDent."
    )


def _routine_office_has_verified_context(context_bundle: dict[str, object]) -> bool:
    return _context_has_real_office_facts(context_bundle)


def _build_routine_no_context_hal_response(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    context_bundle: dict[str, object],
) -> dict[str, object]:
    sanitized = context_bundle.get("sanitized")
    sanitized_question = str(context_bundle.get("sanitized_question") or "")
    findings = sanitized.get("findings", []) if isinstance(sanitized, dict) else []
    answer = _build_routine_no_context_answer_text()
    state = context_bundle.get("state") if isinstance(context_bundle.get("state"), dict) else _get_conversation_state(actor, session_id)
    _update_conversation_state(
        actor=actor,
        session_id=session_id,
        state=state,
        question=question,
        patient_context={"matched": False},
        softdent_aggregate_context=[],
        hardware_review_actions=[],
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="hal-routine-no-context",
        detail=f"Answered a routine office prompt without a verified snapshot for: {sanitized_question[:140]}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:routine-status",
        sanitized_question=sanitized_question,
        retrieval_ids=[],
        response_summary=answer[:180],
    )
    return {
        "mode": f"{HAL_MODE}:routine-status",
        "answer": answer,
        "sanitized_question": sanitized_question,
        "sanitization_findings": findings,
        "retrieved_context": [],
        "guardrails": [
            "approved local read-only scope",
            "deterministic server facts first",
            "read-only data boundary",
            "audit log recorded",
        ],
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "review_actions": [],
        "voice_profile": _voice_profile("primary"),
        "governance_notes": _build_governance_notes(),
    }


def _build_missing_claim_facts_hal_response(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    context_bundle: dict[str, object],
) -> dict[str, object]:
    sanitized = context_bundle.get("sanitized")
    sanitized_question = str(context_bundle.get("sanitized_question") or "")
    findings = sanitized.get("findings", []) if isinstance(sanitized, dict) else []
    answer = _build_missing_claim_facts_answer_text()
    state = context_bundle.get("state") if isinstance(context_bundle.get("state"), dict) else _get_conversation_state(actor, session_id)
    _update_conversation_state(
        actor=actor,
        session_id=session_id,
        state=state,
        question=question,
        patient_context={"matched": False},
        softdent_aggregate_context=[],
        hardware_review_actions=[],
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="hal-missing-claim-facts",
        detail=f"Answered a claim/narrative prompt without verified claim facts for: {sanitized_question[:140]}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:missing-claim-facts",
        sanitized_question=sanitized_question,
        retrieval_ids=[],
        response_summary=answer[:180],
    )
    return {
        "mode": f"{HAL_MODE}:missing-claim-facts",
        "answer": answer,
        "sanitized_question": sanitized_question,
        "sanitization_findings": findings,
        "retrieved_context": [],
        "guardrails": [
            "approved local read-only scope",
            "deterministic server facts first",
            "read-only data boundary",
            "audit log recorded",
        ],
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "review_actions": [],
        "voice_profile": _voice_profile("primary"),
        "governance_notes": _build_governance_notes(),
    }


def _should_escalate_primary_answer(answer: str, *, generation_error: str | None = None) -> bool:
    if generation_error:
        return True
    normalized = answer.strip()
    if not normalized:
        return True
    if normalized.upper().startswith(ESCALATION_MARKER):
        return True
    lowered = normalized.lower()
    escalation_phrases = (
        "cannot determine",
        "can't determine",
        "cannot answer from",
        "can't answer from",
        "insufficient context",
        "not enough information",
        "unable to determine",
        "do not have enough",
        "don't have enough",
        "unable to answer",
    )
    return any(phrase in lowered for phrase in escalation_phrases)


def _strip_escalation_marker(answer: str) -> str:
    normalized = answer.strip()
    if normalized.upper().startswith(ESCALATION_MARKER):
        remainder = normalized[len(ESCALATION_MARKER) :].strip(" :-")
        return remainder
    return normalized


_AR_KEYWORD_PATTERN = re.compile(r"(?i)(accounts?\s+receivable|\bA/?R\b|receivables?)")
_DOLLAR_AMOUNT_PATTERN = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")


def _answer_asserts_ar_amount(answer: str) -> bool:
    """True when an answer presents an accounts-receivable balance as a dollar amount."""
    text = answer or ""
    for match in _DOLLAR_AMOUNT_PATTERN.finditer(text):
        window = text[max(0, match.start() - 60) : match.end() + 60]
        if _AR_KEYWORD_PATTERN.search(window):
            return True
    return False


def _context_contains_verified_ar(combined_context: list[dict[str, object]]) -> bool:
    """True when a context excerpt carries an explicit A/R total with a dollar amount."""
    for item in combined_context:
        if not isinstance(item, dict):
            continue
        excerpt = str(item.get("excerpt") or item.get("content") or "")
        for match in _DOLLAR_AMOUNT_PATTERN.finditer(excerpt):
            window = excerpt[max(0, match.start() - 60) : match.end() + 60]
            if _AR_KEYWORD_PATTERN.search(window):
                return True
    return False


def _model_answer_unsafe_ar(answer: str, combined_context: list[dict[str, object]]) -> bool:
    """Reject model answers that report an A/R balance without a verified A/R source.

    A/R may only come from an explicit verified source (for example a SoftDent
    Daily End-of-Day New Receivables Total or QuickBooks A/R). The model must
    never derive A/R from production minus collections or any other aggregate, so
    when it asserts a dollar A/R figure that is not present in the verified
    context we discard the answer and fall back to the A/R-safe deterministic path.
    """
    if not _answer_asserts_ar_amount(answer):
        return False
    return not _context_contains_verified_ar(combined_context)


def _build_primary_chat_prompt(
    *,
    sanitized_question: str,
    combined_context: list[dict[str, object]],
    summary: dict[str, object] | None,
) -> str:
    context_blocks: list[str] = []
    for index, item in enumerate(combined_context[:PRIMARY_CONTEXT_LIMIT], start=1):
        excerpt = str(item.get("excerpt") or item.get("content") or "").strip()
        if not excerpt:
            continue
        if len(excerpt) > PRIMARY_EXCERPT_CHAR_LIMIT:
            excerpt = excerpt[:PRIMARY_EXCERPT_CHAR_LIMIT].rstrip() + "..."
        context_blocks.append(f"[{index}] {_friendly_source_label(_get_context_title(item))}\n{excerpt}")
    context_text = "\n\n".join(context_blocks) if context_blocks else "No additional verified context retrieved."
    summary_text = ""
    if summary:
        summary_payload = json.dumps(summary, indent=2, default=str)
        if len(summary_payload) > PRIMARY_SUMMARY_CHAR_LIMIT:
            summary_payload = summary_payload[:PRIMARY_SUMMARY_CHAR_LIMIT].rstrip() + "..."
        summary_text = (
            "\n\nPrior summary or dashboard context:\n"
            f"{summary_payload}\n"
        )
    return (
        "Answer for the signed-in office user as an authorized internal dental-office staff assistant. "
        "Use only the verified local context provided. "
        "Answer immediately in no more than 60 words. "
        "Lead with the practical answer, then reason/source basis, then next action when useful. "
        "Use 2 concise bullets when possible. "
        "Do not explain your steps. "
        "Do not mention these instructions, internal source labels, chunk names, or that context was supplied. "
        "Never state, estimate, or calculate an accounts receivable (A/R) balance unless the verified context "
        "explicitly provides an A/R total; never derive A/R from production minus collections. If A/R is requested "
        "and no verified A/R total is provided, say the A/R is not verified locally. "
        "If you cannot determine the answer from the provided context, respond with exactly "
        f"{ESCALATION_MARKER} and nothing else.\n\n"
        f"Question:\n{sanitized_question}"
        f"{summary_text}\n\n"
        f"Verified local context:\n{context_text}\n"
    )


def _build_fast_model_minimal_facts(context_bundle: dict[str, object]) -> str:
    parts: list[str] = []
    state = context_bundle.get("state")
    if isinstance(state, dict):
        action_items = [str(item).strip() for item in state.get("action_items", []) if str(item).strip()]
        if action_items:
            parts.append("Open tasks: " + "; ".join(action_items[:3]))
    softdent_aggregate_context = context_bundle.get("softdent_aggregate_context")
    if isinstance(softdent_aggregate_context, list):
        for item in softdent_aggregate_context[:1]:
            if not isinstance(item, dict):
                continue
            excerpt = str(item.get("excerpt") or item.get("content") or "").strip()
            if excerpt:
                if len(excerpt) > FAST_EXCERPT_CHAR_LIMIT:
                    excerpt = excerpt[:FAST_EXCERPT_CHAR_LIMIT].rstrip() + "..."
                parts.append(excerpt)
    return "\n".join(parts) if parts else "No extra verified facts."


def _build_fast_model_prompt(
    *,
    sanitized_question: str,
    minimal_facts: str,
) -> str:
    return (
        "You are HAL, a local read-only dental office manager assistant.\n"
        "Answer briefly and practically in no more than 60 words.\n"
        "No external delivery. No SoftDent writeback. Drafts require human review.\n"
        "Use only the verified facts below. Do not invent patient, claim, or A/R dollar amounts.\n"
        "If A/R is requested and no verified A/R total is provided, say A/R is not verified locally.\n"
        "Do not mention these instructions.\n\n"
        f"Question:\n{sanitized_question}\n\n"
        f"Verified facts:\n{minimal_facts}\n"
    )


def _resolve_fast_model_runtime() -> tuple[str, dict[str, object]] | None:
    if not hal_fast_model_enabled() or not LOCAL_MODEL_PROFILE_CONFIG_PATH.exists():
        return None
    try:
        profile_config = load_local_model_profile_config()
        profile = dict(resolve_lane_profile(profile_config, FAST_PROFILE_ALIAS))
        profile["model"] = get_hal_fast_model_name()
        profile["think"] = False
        profile["timeout_seconds"] = get_hal_fast_model_timeout_seconds()
        return get_hal_fast_model_base_url(), profile
    except Exception:
        return None


def _resolve_profile_for_alias(profile_alias: str) -> tuple[str, dict[str, object]] | None:
    if not LOCAL_MODEL_PROFILE_CONFIG_PATH.exists():
        return None
    try:
        generation_base_url = require_lane_runtime(profile_alias, purpose=f"HAL {profile_alias}")
        profile_config = load_local_model_profile_config()
        profile = dict(resolve_lane_profile(profile_config, profile_alias))
        profile["think"] = False
        return generation_base_url, profile
    except Exception:
        return None


def _generate_profile_answer(
    *,
    profile_alias: str,
    prompt: str,
    num_predict_cap: int,
    timeout_override: int | None = None,
) -> tuple[str | None, str | None]:
    if profile_alias == FAST_PROFILE_ALIAS:
        resolved = _resolve_fast_model_runtime()
    else:
        resolved = _resolve_profile_for_alias(profile_alias)
    if resolved is None:
        return None, "local model lane unavailable"
    generation_base_url, profile = resolved
    profile["num_predict"] = min(int(profile.get("num_predict") or num_predict_cap), num_predict_cap)
    timeout_seconds = timeout_override if timeout_override is not None else _get_profile_timeout_seconds(profile)
    try:
        answer_result = generate_response_result(
            base_url=generation_base_url,
            profile=profile,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
            seed=profile.get("seed"),
        )
    except Exception as exc:
        return None, str(exc)
    answer = str(answer_result.get("response_text") or "").strip()
    if not answer:
        return None, "empty model response"
    return answer, None


def _build_model_hal_response(
    *,
    actor: str,
    question: str,
    session_id: str | None,
    context_bundle: dict[str, object],
    answer: str,
    voice_profile_name: str,
    mode_suffix: str,
    guardrail_extras: list[str],
    answer_lane: str,
    model_used: str | None = None,
    escalated: bool = False,
    routing_elapsed_ms: int | None = None,
) -> dict[str, object]:
    state = context_bundle["state"]
    patient_context = context_bundle["patient_context"]
    sanitized = context_bundle["sanitized"]
    sanitized_question = str(context_bundle["sanitized_question"])
    hardware_review_actions = context_bundle["hardware_review_actions"]
    softdent_aggregate_context = context_bundle["softdent_aggregate_context"]
    combined_context = context_bundle["combined_context"]
    answer = _append_governed_memory_proposal(
        _sanitize_staff_facing_answer(_strip_escalation_marker(answer)), question=question
    )
    _update_conversation_state(
        actor=actor,
        session_id=session_id,
        state=state,
        question=question,
        patient_context=patient_context,
        softdent_aggregate_context=softdent_aggregate_context,
        hardware_review_actions=hardware_review_actions,
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="hal-ask-model",
        detail=f"Answered a HAL question via {voice_profile_name} for sanitized request: {sanitized_question[:140]}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:{mode_suffix}",
        sanitized_question=sanitized_question,
        retrieval_ids=[_get_context_source_id(item) for item in combined_context if isinstance(item, dict)],
        response_summary=answer[:180],
    )
    patient_matched = bool(patient_context.get("matched")) if isinstance(patient_context, dict) else False
    return _attach_routing_metadata(
        {
            "mode": f"{HAL_MODE}:{mode_suffix}",
            "answer": answer,
            "sanitized_question": sanitized_question,
            "sanitization_findings": sanitized.get("findings", []),
            "retrieved_context": combined_context,
            "guardrails": [
                "approved local read-only scope",
                "sanitized retrieval only",
                "read-only data boundary",
                "truthful runtime claims only",
                "audit log recorded",
                "hardware mutations require human confirmation",
                "tier-1 critical actions require explicit confirmation",
                "tier-2 mismatches raise [ALERT]",
                "tier-3 assistance stays concise",
            ]
            + guardrail_extras
            + (["authorized internal office context"] if patient_matched else []),
            "audit_id": audit_entry["audit_id"],
            "access_policy": get_hal_access_policy(),
            "review_actions": hardware_review_actions,
            "voice_profile": _voice_profile(voice_profile_name),
            "governance_notes": _build_governance_notes(
                patient_context_used=patient_matched,
                review_actions_present=bool(hardware_review_actions),
            ),
        },
        answer_lane=answer_lane,
        model_used=model_used,
        escalated=escalated,
        routing_elapsed_ms=routing_elapsed_ms,
    )


def _try_hal_fast_model_answer(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    context_bundle: dict[str, object],
    routing_started_at: float,
) -> dict[str, object] | None:
    if not hal_fast_model_enabled() or not _hal_ask_model_routing_enabled():
        return None
    sanitized_question = str(context_bundle["sanitized_question"])
    combined_context = context_bundle["combined_context"]
    context_list = combined_context if isinstance(combined_context, list) else []
    minimal_facts = _build_fast_model_minimal_facts(context_bundle)
    prompt = _build_fast_model_prompt(
        sanitized_question=sanitized_question,
        minimal_facts=minimal_facts,
    )
    fast_answer, fast_error = _generate_profile_answer(
        profile_alias=FAST_PROFILE_ALIAS,
        prompt=prompt,
        num_predict_cap=FAST_NUM_PREDICT,
        timeout_override=get_hal_fast_model_timeout_seconds(),
    )
    if not fast_answer or _should_escalate_primary_answer(fast_answer, generation_error=fast_error):
        return None
    if _model_answer_unsafe_ar(fast_answer, context_list):
        return None
    elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
    return _build_model_hal_response(
        actor=actor,
        question=question,
        session_id=session_id,
        context_bundle=context_bundle,
        answer=fast_answer,
        voice_profile_name="fast_office",
        mode_suffix="fast-chat",
        guardrail_extras=["fast office model response"],
        answer_lane="fast_model",
        model_used=get_hal_fast_model_name(),
        escalated=False,
        routing_elapsed_ms=elapsed_ms,
    )


def _try_hal_model_answer_with_escalation(
    *,
    question: str,
    actor: str,
    summary: dict[str, object] | None,
    session_id: str | None,
    context_bundle: dict[str, object],
    routing_started_at: float | None = None,
) -> dict[str, object] | None:
    if not _hal_ask_model_routing_enabled():
        return None
    started = routing_started_at or time.monotonic()
    sanitized_question = str(context_bundle["sanitized_question"])
    combined_context = context_bundle["combined_context"]
    context_list = combined_context if isinstance(combined_context, list) else []
    if _is_operational_prompt(question, context_bundle):
        context_list = [
            item
            for item in context_list
            if isinstance(item, dict) and _is_verified_operational_context_item(item)
        ]

    def _is_usable(answer: str | None, *, generation_error: str | None) -> bool:
        if not answer:
            return False
        if _should_escalate_primary_answer(answer, generation_error=generation_error):
            return False
        # Never let the free-form model surface an A/R balance without a verified
        # source; fall back to the A/R-safe deterministic path instead.
        if _model_answer_unsafe_ar(answer, context_list):
            return False
        return True

    primary_prompt = _build_primary_chat_prompt(
        sanitized_question=sanitized_question,
        combined_context=context_list,
        summary=summary,
    )
    primary_answer, primary_error = _generate_profile_answer(
        profile_alias=PRIMARY_PROFILE_ALIAS,
        prompt=primary_prompt,
        num_predict_cap=PRIMARY_NUM_PREDICT,
        timeout_override=get_hal_main_model_timeout_seconds(),
    )
    if _is_usable(primary_answer, generation_error=primary_error):
        return _build_model_hal_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=primary_answer,
            voice_profile_name="primary",
            mode_suffix="chat",
            guardrail_extras=["frontline 14B model response"],
            answer_lane="primary",
            model_used=get_frontend_model_name(),
            escalated=False,
            routing_elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    escalation_prompt = _build_second_opinion_prompt(
        sanitized_question=sanitized_question,
        combined_context=context_list,
        summary=summary,
    )
    deeper_answer, deeper_error = _generate_profile_answer(
        profile_alias=SECOND_OPINION_PROFILE_ALIAS,
        prompt=escalation_prompt,
        num_predict_cap=SECOND_OPINION_NUM_PREDICT,
    )
    if _is_usable(deeper_answer, generation_error=deeper_error):
        return _build_model_hal_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=deeper_answer,
            voice_profile_name="deeper_review",
            mode_suffix="deeper-review",
            guardrail_extras=[
                "internal 30B deeper review after frontline answer was inconclusive",
            ],
            answer_lane="fallback",
            model_used=get_backend_model_name(),
            escalated=True,
            routing_elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    if _is_usable(primary_answer, generation_error=None):
        return _build_model_hal_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=primary_answer,
            voice_profile_name="primary",
            mode_suffix="chat",
            guardrail_extras=["frontline 14B model response"],
            answer_lane="primary",
            model_used=get_frontend_model_name(),
            escalated=False,
            routing_elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    del primary_error, deeper_error
    return None


def _build_deterministic_hal_answer(
    *,
    question: str,
    actor: str,
    session_id: str | None,
    context_bundle: dict[str, object],
) -> dict[str, object]:
    state = context_bundle["state"]
    patient_context = context_bundle["patient_context"]
    sanitized = context_bundle["sanitized"]
    sanitized_question = str(context_bundle["sanitized_question"])
    hardware_context = context_bundle["hardware_context"]
    hardware_review_actions = context_bundle["hardware_review_actions"]
    softdent_aggregate_context = context_bundle["softdent_aggregate_context"]
    live_report_context = context_bundle["live_report_context"]
    combined_context = context_bundle["combined_context"]
    operating_picture = context_bundle["operating_picture"]
    context_titles = ", ".join(_get_context_title(item) for item in combined_context)
    lowered_question = question.lower()
    if patient_context["matched"]:
        patient_summary = _build_patient_context_summary(patient_context)
        summary_fields = patient_context.get("summary_fields") if isinstance(patient_context.get("summary_fields"), dict) else {}
        patient_name = str(summary_fields.get("patient_name") or "the patient")
        if _is_patient_ar_balance_question(question) and not _patient_level_softdent_ar_export_available():
            answer = _build_missing_patient_ar_answer(patient_name)
            if context_titles:
                answer += f" Supporting context: {context_titles}."
        elif _is_patient_follow_up_question(question) and ("follow-up plan" in lowered_question or "follow up plan" in lowered_question):
            answer = (
                (f"Verified patient context: {patient_summary}. " if patient_summary else "")
                + _build_patient_follow_up_plan(patient_context)
                + (f" Supporting context: {context_titles}." if context_titles else "")
            )
        else:
            answer = (
                (f"Verified patient context: {patient_summary}. " if patient_summary else "")
                + f"{patient_context['narrative']}"
                + (f" Supporting context: {context_titles}." if context_titles else "")
            )
        voice_profile = _voice_profile("patient_workflow")
        governance_notes = _build_governance_notes(patient_context_used=True)
    else:
        context_items_for_summary = combined_context
        if _is_operational_prompt(question, context_bundle):
            context_items_for_summary = [
                item
                for item in combined_context
                if isinstance(item, dict) and _is_verified_operational_context_item(item)
            ]
        context_summary = _build_context_excerpt_summary(context_items_for_summary)
        hardware_summary = _build_hardware_answer_summary(hardware_context)
        softdent_summary = _build_softdent_answer_summary(softdent_aggregate_context)
        report_summary = _build_report_answer_summary(live_report_context)
        answer_parts: list[str] = []
        concise_answer_frame = _should_use_concise_answer_frame(question)
        # Focused status answers (A/R availability, missing exports) are
        # self-contained. They must not trail QuickBooks/source-health
        # diagnostics, raw report metrics, or retrieved context excerpts into the
        # staff-facing answer.
        focused_status_answer = (
            _is_ar_availability_question(question)
            or _is_missing_exports_question(question)
            or _is_claim_packet_readiness_question(question)
        )
        include_operating_picture = _is_operating_picture_request(question) and not _is_follow_up_question(question)
        if include_operating_picture and not concise_answer_frame:
            answer_parts.append(f"{operating_picture['summary']} I answer from deterministic server facts first, then from approved local retrieval.")
        if _is_quickbooks_write_request(question):
            answer_parts.append(_build_quickbooks_write_boundary_answer())
        elif _is_collections_follow_up_request(question) and any(str(item.get("source_id") or "") == "softdent-live-collection-delta" for item in softdent_aggregate_context):
            answer_parts.append(_build_collections_follow_up_answer(softdent_aggregate_context))
        elif _is_weakest_provider_request(question):
            answer_parts.append(_build_weakest_provider_answer(softdent_aggregate_context))
        elif _is_action_summary_request(question):
            answer_parts.append(_build_action_summary_answer([str(item) for item in state.get("action_items", []) if str(item).strip()]))
        elif _is_ar_availability_question(question):
            answer_parts.append(_build_ar_availability_status_answer())
        elif _is_missing_exports_question(question):
            answer_parts.append(_build_missing_exports_status_answer())
        elif _is_claim_packet_readiness_question(question):
            answer_parts.append(_build_claim_packet_readiness_status_answer(actor=actor))
        if include_operating_picture and not concise_answer_frame:
            answer_parts.append(
                "I can use sanitized financial summaries, KPI context, approved SoftDent aggregate snapshots, sanitized SoftDent claims or clinical-note exports when available, and approved QuickBooks read-only summaries only."
            )
            answer_parts.append(
                "Priority routing applies: Tier 1 critical actions stay proposal-only until a human explicitly confirms them; Tier 2 read-and-analyze work stays read-only and must raise [ALERT] on mismatches; Tier 3 assistance stays concise and fast."
            )
        if not focused_status_answer:
            if hardware_summary:
                answer_parts.append(f"Verified hardware metrics: {hardware_summary}")
            if softdent_summary:
                answer_parts.append(f"Verified SoftDent metrics: {softdent_summary}")
            if report_summary:
                answer_parts.append(f"Verified report metrics: {report_summary}")
                for item in live_report_context:
                    if str(item.get("source_id") or "").startswith("qb-"):
                        answer_parts.append(_get_context_title(item))
                        break
        if hardware_review_actions:
            answer_parts.append("Requested hardware changes require human confirmation before any device command is sent.")
        if not focused_status_answer and context_summary:
            answer_parts.append(context_summary)
        if _user_asked_for_sources(question):
            friendly_sources = _summarize_sources_for_display(combined_context)
            if friendly_sources:
                answer_parts.append(f"Sources used: {friendly_sources}.")
        if not answer_parts:
            answer_parts.append(
                "I can review approved local office context for a specific patient, claim, metric, or task. "
                "I stay local/read-only and do not submit, send, upload, or write back to SoftDent."
            )
        answer = _dedupe_answer_parts(answer_parts)
        voice_profile = _voice_profile("primary")
        governance_notes = _build_governance_notes(review_actions_present=bool(hardware_review_actions))
    answer = _append_governed_memory_proposal(answer, question=question)
    _update_conversation_state(
        actor=actor,
        session_id=session_id,
        state=state,
        question=question,
        patient_context=patient_context,
        softdent_aggregate_context=softdent_aggregate_context,
        hardware_review_actions=hardware_review_actions,
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="read-approved-hal-context",
        detail=f"Answered a HAL question from approved context for sanitized request: {sanitized_question[:140]}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=HAL_MODE,
        sanitized_question=sanitized_question,
        retrieval_ids=[_get_context_source_id(item) for item in combined_context],
        response_summary=answer[:180],
    )
    return {
        "mode": HAL_MODE,
        "answer": answer,
        "sanitized_question": sanitized_question,
        "sanitization_findings": sanitized["findings"],
        "retrieved_context": combined_context,
        "guardrails": [
            "approved local read-only scope",
            "deterministic server facts first",
            "sanitized retrieval only",
            "read-only data boundary",
            "approved summary queries only",
            "truthful runtime claims only",
            "audit log recorded",
            "hardware mutations require human confirmation",
            "tier-1 critical actions require explicit confirmation",
            "tier-2 mismatches raise [ALERT]",
            "tier-3 assistance stays concise",
        ] + (["authorized internal office context"] if patient_context["matched"] else []),
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "review_actions": hardware_review_actions,
        "voice_profile": voice_profile,
        "governance_notes": governance_notes,
    }


def answer_hal_question(
    *,
    question: str,
    actor: str,
    summary: dict[str, object] | None = None,
    session_id: str | None = None,
    roles: object | None = None,
) -> dict[str, object]:
    routing_started_at = time.monotonic()

    if _is_generic_help_request(question):
        cache_key = "generic_help"
        cached = _get_cached_deterministic_response(cache_key)
        if cached is not None:
            elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
            result = _attach_routing_metadata(cached, answer_lane="deterministic", routing_elapsed_ms=elapsed_ms)
            _log_hal_routing(
                question=question,
                answer_lane="deterministic",
                model_used=None,
                escalated=False,
                routing_elapsed_ms=elapsed_ms,
                model_called=False,
            )
            return result
        sanitized = sanitize_hal_text(question)
        payload = _build_generic_help_hal_response(
            question=question,
            actor=actor,
            session_id=session_id,
            sanitized=sanitized,
        )
        _store_cached_deterministic_response(cache_key, payload)
        elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
        result = _attach_routing_metadata(payload, answer_lane="deterministic", routing_elapsed_ms=elapsed_ms)
        _log_hal_routing(
            question=question,
            answer_lane="deterministic",
            model_used=None,
            escalated=False,
            routing_elapsed_ms=elapsed_ms,
            model_called=False,
        )
        return result

    context_bundle = _collect_hal_question_context(
        question=question, actor=actor, session_id=session_id, roles=roles
    )
    deterministic_result: dict[str, object] | None = None
    if _hal_ask_fast_path_enabled():
        if (
            _is_ar_availability_question(question)
            or _is_missing_exports_question(question)
            or _is_claim_packet_readiness_question(question)
        ):
            cache_key = f"status:{_normalize_help_question(question)}"
            cached = _get_cached_deterministic_response(cache_key)
            if cached is not None:
                elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
                result = _attach_routing_metadata(cached, answer_lane="deterministic", routing_elapsed_ms=elapsed_ms)
                _log_hal_routing(
                    question=question,
                    answer_lane="deterministic",
                    model_used=None,
                    escalated=False,
                    routing_elapsed_ms=elapsed_ms,
                    model_called=False,
                )
                return result
        deterministic_result = _build_deterministic_hal_answer(
            question=question,
            actor=actor,
            session_id=session_id,
            context_bundle=context_bundle,
        )
        patient_context = context_bundle.get("patient_context")
        patient_matched = bool(patient_context.get("matched")) if isinstance(patient_context, dict) else False
        if _should_allow_deterministic_short_circuit(
            question=question,
            context_bundle=context_bundle,
            answer=str(deterministic_result.get("answer") or ""),
            patient_matched=patient_matched,
        ):
            if (
            _is_ar_availability_question(question)
            or _is_missing_exports_question(question)
            or _is_claim_packet_readiness_question(question)
        ):
                cache_key = f"status:{_normalize_help_question(question)}"
                _store_cached_deterministic_response(cache_key, deterministic_result)
            elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
            result = _attach_routing_metadata(
                deterministic_result,
                answer_lane="deterministic",
                routing_elapsed_ms=elapsed_ms,
            )
            _log_hal_routing(
                question=question,
                answer_lane="deterministic",
                model_used=None,
                escalated=False,
                routing_elapsed_ms=elapsed_ms,
                model_called=False,
            )
            return result

    if _is_routine_office_question(question, context_bundle) and not _routine_office_has_verified_context(context_bundle):
        payload = _build_routine_no_context_hal_response(
            question=question,
            actor=actor,
            session_id=session_id,
            context_bundle=context_bundle,
        )
        elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
        result = _attach_routing_metadata(payload, answer_lane="deterministic", routing_elapsed_ms=elapsed_ms)
        _log_hal_routing(
            question=question,
            answer_lane="deterministic",
            model_used=None,
            escalated=False,
            routing_elapsed_ms=elapsed_ms,
            model_called=False,
        )
        return result

    if _is_routine_office_question(question, context_bundle):
        fast_result = _try_hal_fast_model_answer(
            question=question,
            actor=actor,
            session_id=session_id,
            context_bundle=context_bundle,
            routing_started_at=routing_started_at,
        )
        if fast_result is not None:
            _log_hal_routing(
                question=question,
                answer_lane=str(fast_result.get("answer_lane") or "fast_model"),
                model_used=str(fast_result.get("model_used") or get_hal_fast_model_name()),
                escalated=bool(fast_result.get("escalated")),
                routing_elapsed_ms=int(fast_result.get("routing_elapsed_ms") or 0),
                model_called=True,
            )
            return fast_result

    if (
        _is_claim_or_narrative_prompt(question)
        and not _context_has_real_office_facts(context_bundle)
        and _context_is_documentation_or_diagnostic_only(context_bundle)
    ):
        payload = _build_missing_claim_facts_hal_response(
            question=question,
            actor=actor,
            session_id=session_id,
            context_bundle=context_bundle,
        )
        elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
        result = _attach_routing_metadata(payload, answer_lane="deterministic", routing_elapsed_ms=elapsed_ms)
        _log_hal_routing(
            question=question,
            answer_lane="deterministic",
            model_used=None,
            escalated=False,
            routing_elapsed_ms=elapsed_ms,
            model_called=False,
        )
        return result

    model_result = _try_hal_model_answer_with_escalation(
        question=question,
        actor=actor,
        summary=summary,
        session_id=session_id,
        context_bundle=context_bundle,
        routing_started_at=routing_started_at,
    )
    if model_result is not None:
        _log_hal_routing(
            question=question,
            answer_lane=str(model_result.get("answer_lane") or "primary"),
            model_used=str(model_result.get("model_used") or ""),
            escalated=bool(model_result.get("escalated")),
            routing_elapsed_ms=int(model_result.get("routing_elapsed_ms") or 0),
            model_called=True,
        )
        return model_result
    if deterministic_result is not None:
        elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
        result = _attach_routing_metadata(
            deterministic_result,
            answer_lane="deterministic",
            routing_elapsed_ms=elapsed_ms,
        )
        _log_hal_routing(
            question=question,
            answer_lane="deterministic",
            model_used=None,
            escalated=False,
            routing_elapsed_ms=elapsed_ms,
            model_called=False,
        )
        return result
    final = _build_deterministic_hal_answer(
        question=question,
        actor=actor,
        session_id=session_id,
        context_bundle=context_bundle,
    )
    elapsed_ms = int((time.monotonic() - routing_started_at) * 1000)
    result = _attach_routing_metadata(final, answer_lane="deterministic", routing_elapsed_ms=elapsed_ms)
    _log_hal_routing(
        question=question,
        answer_lane="deterministic",
        model_used=None,
        escalated=False,
        routing_elapsed_ms=elapsed_ms,
        model_called=False,
    )
    return result


def answer_hal_second_opinion_question(
    *,
    question: str,
    actor: str,
    summary: dict[str, object] | None = None,
    session_id: str | None = None,
    roles: object | None = None,
) -> dict[str, object]:
    if _is_patient_claims_second_opinion_question(question):
        context_bundle = _collect_patient_claims_second_opinion_context(
            question=question, actor=actor, session_id=session_id, roles=roles
        )
        answer, claims_audit_meta = _build_immediate_patient_claims_second_opinion(context_bundle)
        return _build_second_opinion_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=answer,
            deterministic_claims_fast_path=True,
            claims_audit_meta=claims_audit_meta,
        )
    context_bundle = _collect_hal_question_context(
        question=question, actor=actor, session_id=session_id, roles=roles
    )

    if not LOCAL_MODEL_PROFILE_CONFIG_PATH.exists():
        unavailable_message = (
            "Local model profile config is missing; second opinion requires the backend local AI lane."
        )
        return _build_second_opinion_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=f"Second opinion unavailable. {unavailable_message}",
            local_ai_unavailable=unavailable_message,
        )

    try:
        generation_base_url = require_lane_runtime(
            SECOND_OPINION_PROFILE_ALIAS,
            purpose="HAL second opinion",
        )
    except LocalAIConfigError as exc:
        unavailable_message = _format_backend_lane_unavailable_message(exc)
        return _build_second_opinion_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=f"Second opinion unavailable. {unavailable_message}",
            local_ai_unavailable=unavailable_message,
        )

    try:
        profile_config = load_local_model_profile_config()
        second_opinion_profile = dict(resolve_lane_profile(profile_config, SECOND_OPINION_PROFILE_ALIAS))
        second_opinion_profile["num_predict"] = min(
            int(second_opinion_profile.get("num_predict") or SECOND_OPINION_NUM_PREDICT),
            SECOND_OPINION_NUM_PREDICT,
        )
        second_opinion_profile["think"] = False
    except Exception as exc:
        unavailable_message = f"Local model profile config could not be loaded: {exc}"
        return _build_second_opinion_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=f"Second opinion unavailable. {unavailable_message}",
            local_ai_unavailable=unavailable_message,
        )

    prompt = _build_second_opinion_prompt(
        sanitized_question=str(context_bundle["sanitized_question"]),
        combined_context=context_bundle["combined_context"],
        summary=summary,
    )
    try:
        answer_result = generate_response_result(
            base_url=generation_base_url,
            profile=second_opinion_profile,
            prompt=prompt,
            timeout_seconds=_get_profile_timeout_seconds(second_opinion_profile),
            seed=second_opinion_profile.get("seed"),
        )
    except Exception as exc:
        unavailable_message = f"Backend local AI second opinion failed: {exc}"
        return _build_second_opinion_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=f"Second opinion unavailable. {unavailable_message}",
            local_ai_unavailable=unavailable_message,
        )

    answer = str(answer_result.get("response_text") or "").strip()
    if not answer:
        unavailable_message = "Backend local AI returned an empty second opinion."
        return _build_second_opinion_response(
            actor=actor,
            question=question,
            session_id=session_id,
            context_bundle=context_bundle,
            answer=f"Second opinion unavailable. {unavailable_message}",
            local_ai_unavailable=unavailable_message,
        )

    return _build_second_opinion_response(
        actor=actor,
        question=question,
        session_id=session_id,
        context_bundle=context_bundle,
        answer=answer,
    )


def answer_insurance_narrative_request(*, question: str, actor: str, roles: object | None = None) -> dict[str, object]:
    patient_context = get_controlled_patient_context(
        question, roles=roles, actor=actor, workflow_reason="insurance_narrative", response_mode="narrative_draft"
    )
    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"])

    if patient_context["matched"]:
        patient_summary = _build_patient_context_summary(patient_context)
        narrative = (f"Verified patient context: {patient_summary}. " if patient_summary else "") + str(patient_context["narrative"])
        supporting_context = list(patient_context["snippets"])
    else:
        narrative = (
            "No patient-specific SoftDent claims or clinical-note rows matched this request. "
            "Verify that the approved exports contain the patient identifiers and claim documentation needed for narrative generation."
        )
        supporting_context = []

    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:insurance-narrative",
        sanitized_question=sanitized_question,
        retrieval_ids=[_get_context_source_id(item) for item in supporting_context],
        response_summary=narrative[:180],
    )
    return {
        "mode": HAL_MODE,
        "matched": bool(patient_context["matched"]),
        "narrative": narrative,
        "sanitized_question": sanitized_question,
        "sanitization_findings": sanitized["findings"],
        "supporting_context": supporting_context,
        "guardrails": [
            "approved local read-only scope",
            "patient-specific local tool only",
            "authorized internal office context",
            "sanitized audit trail",
            "review before submission",
            "no external submission performed",
        ],
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "voice_profile": _voice_profile("patient_workflow"),
        "governance_notes": _build_governance_notes(patient_context_used=bool(patient_context["matched"])),
    }


def answer_patient_dossier_request(*, question: str, actor: str, roles: object | None = None) -> dict[str, object]:
    patient_context = get_controlled_patient_context(
        question, roles=roles, actor=actor, workflow_reason="patient_dossier"
    )
    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"])

    if patient_context["matched"]:
        patient_summary = _build_patient_context_summary(patient_context)
        summary = "Patient-specific SoftDent claim and/or clinical-note context matched in the approved local exports."
        if patient_summary:
            summary += f" Verified patient context: {patient_summary}."
        supporting_context = list(patient_context["snippets"])
    else:
        summary = (
            "No patient-specific SoftDent claims or clinical-note rows matched this lookup. "
            "Verify that the approved exports exist and include patient identifiers for the requested chart or claim."
        )
        supporting_context = []

    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:patient-dossier",
        sanitized_question=sanitized_question,
        retrieval_ids=[_get_context_source_id(item) for item in supporting_context],
        response_summary=summary[:180],
    )
    return {
        "mode": HAL_MODE,
        "matched": bool(patient_context["matched"]),
        "summary": summary,
        "sanitized_question": sanitized_question,
        "sanitization_findings": sanitized["findings"],
        "supporting_context": supporting_context,
        "guardrails": [
            "approved local read-only scope",
            "patient-specific local tool only",
            "authorized internal office context",
            "sanitized audit trail",
            "no external submission performed",
        ],
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "voice_profile": _voice_profile("patient_workflow"),
        "governance_notes": _build_governance_notes(patient_context_used=bool(patient_context["matched"])),
    }


def answer_accounting_policy_question(
    *,
    question: str,
    topic: str | None,
    accounting_standard: str | None,
    actor: str,
) -> dict[str, object]:
    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"])
    retrieval_query = " ".join(part for part in [topic or "", accounting_standard or "", sanitized_question, "accounting policy"] if part).strip()
    retrieved_context = retrieve_relevant_context(retrieval_query, limit=4)
    citations = [
        {
            "source_id": _get_context_source_id(item),
            "title": _get_context_title(item),
            "excerpt": str(item.get("excerpt") or "").strip(),
        }
        for item in retrieved_context
    ]
    citation_titles = ", ".join(item["title"] for item in citations) if citations else "approved local policy sources"
    standard_label = accounting_standard or "internal reviewed guidance"
    answer = (
        f"For this request, HAL found relevant guidance from {citation_titles}. "
        f"Treat this as draft guidance under {standard_label}. A human reviewer should confirm the final accounting treatment before anything reaches the ledger."
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="analyze-accounting-policy",
        detail=f"Reviewed accounting policy context for sanitized request: {sanitized_question[:140]}",
    )
    confidence = "medium" if retrieved_context else "low"
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:accounting-policy",
        sanitized_question=sanitized_question,
        retrieval_ids=[item["source_id"] for item in citations],
        response_summary=answer[:180],
    )
    return {
        "mode": HAL_MODE,
        "answer": answer,
        "accounting_standard": accounting_standard,
        "citations": citations,
        "confidence": confidence,
        "review_required": True,
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "voice_profile": _voice_profile("policy"),
        "governance_notes": [
            _governance_note("Draft-only guidance", "Accounting policy answers are advisory and require human accounting review before operational use."),
            _governance_note("Approved sources", f"This answer was grounded in {citation_titles}."),
        ],
    }


def draft_accounting_journal_entry(
    *,
    description: str,
    transaction_date: str,
    accounting_period: str,
    amount: float,
    context: dict[str, object],
    actor: str,
) -> dict[str, object]:
    sanitized = sanitize_hal_text(description)
    sanitized_description = str(sanitized["sanitized_text"])
    supporting_context = retrieve_relevant_context(sanitized_description)
    generated_summary: str | None = None
    generated_transaction_type: str | None = None
    used_local_ai_workflow = False
    local_ai_unavailable: str | None = None
    workflow_result = _try_local_ai_journal_draft(
        description=sanitized_description,
        accounting_period=accounting_period,
        amount=amount,
        context=context,
    )
    if workflow_result is None:
        lines = draft_journal_entry_for_common_case(
            description=sanitized_description,
            accounting_period=accounting_period,
            amount=amount,
            context=context,
        )
    elif workflow_result.get("local_ai_unavailable"):
        local_ai_unavailable = str(workflow_result["local_ai_unavailable"])
        lines = draft_journal_entry_for_common_case(
            description=sanitized_description,
            accounting_period=accounting_period,
            amount=amount,
            context=context,
        )
    else:
        lines = workflow_result["lines"]
        generated_summary = str(workflow_result["summary"])
        generated_transaction_type = str(workflow_result["transaction_type"])
        used_local_ai_workflow = True
    validation = build_journal_validation(
        lines=lines,
        chart_of_accounts=get_chart_of_accounts(),
        open_period=is_period_open(accounting_period),
    )
    summary = generated_summary or (
        f"Drafted {len(lines)} journal line(s) for review from sanitized accounting input. "
        f"Balanced={validation['balanced']}. Open period={validation['open_period']}."
    )
    if local_ai_unavailable:
        summary = f"{summary} Local AI workflow unavailable; used rule-based fallback. {local_ai_unavailable}"
    review_plan_path = write_review_step_file(
        tier="tier_1",
        actor=actor,
        action="accounting-journal-draft",
        summary=summary,
        payload={
            "description": sanitized_description,
            "transaction_date": transaction_date,
            "accounting_period": accounting_period,
            "amount": round(amount, 2),
            "lines": lines,
            "validation": validation,
            "review_required": True,
        },
    )
    append_ai_activity_log(
        tier="tier_1",
        actor=actor,
        action="prepare-journal-draft",
        detail=f"Prepared a draft-only journal entry for human review. Review plan: {review_plan_path}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:journal-draft",
        sanitized_question=sanitized_description,
        retrieval_ids=[_get_context_source_id(item) for item in supporting_context],
        response_summary=summary[:180],
    )
    draft_status = DRAFT_STATUS_DRAFT_ONLY
    queue_id: str | None = None
    queue_status: str | None = None
    enqueue_error: str | None = None

    if used_local_ai_workflow and _context_flag_enabled(context, "auto_enqueue_validated_draft"):
        try:
            queue_entry = queue_accounting_posting_draft(
                description=sanitized_description,
                transaction_date=transaction_date,
                accounting_period=accounting_period,
                amount=amount,
                transaction_type=generated_transaction_type,
                lines=lines,
                source_audit_id=audit_entry["audit_id"],
                enqueue_mode=ENQUEUE_MODE_AUTO_VALIDATED_AI,
                actor=actor,
            )
        except Exception as exc:
            enqueue_error = f"Failed to auto-enqueue validated draft: {exc}"
        else:
            draft_status = DRAFT_STATUS_ENQUEUED
            queue_id = str(queue_entry["queue_id"])
            queue_status = str(queue_entry["status"])

    return {
        "mode": HAL_MODE,
        "summary": summary,
        "lines": lines,
        "validation": validation,
        "supporting_context": supporting_context,
        "review_required": True,
        "review_plan_path": review_plan_path,
        "draft_status": draft_status,
        "queue_id": queue_id,
        "queue_status": queue_status,
        "enqueue_error": enqueue_error,
        "local_ai_unavailable": local_ai_unavailable,
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
    }


def queue_accounting_posting_draft(
    *,
    description: str,
    transaction_date: str,
    accounting_period: str,
    amount: float,
    transaction_type: str | None,
    lines: list[dict[str, object]],
    source_audit_id: str,
    enqueue_mode: str | None = None,
    actor: str,
) -> dict[str, object]:
    sanitized = sanitize_hal_text(description)
    sanitized_description = str(sanitized["sanitized_text"])
    validation = build_journal_validation(
        lines=lines,
        chart_of_accounts=get_chart_of_accounts(),
        open_period=is_period_open(accounting_period),
    )
    if (
        not validation["balanced"]
        or not validation["account_validation_passed"]
        or not validation["amount_validation_passed"]
        or not validation["open_period"]
    ):
        raise ValueError("Only balanced, valid, open-period drafts can be queued for QuickBooks Desktop review.")

    entry = {
        "queue_id": f"qbd-queue-{uuid4().hex[:12]}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "target_system": "quickbooks_desktop",
        "status": POSTING_QUEUE_STATUS_PENDING_REVIEW,
        "description": sanitized_description,
        "transaction_date": transaction_date,
        "accounting_period": accounting_period,
        "amount": round(amount, 2),
        "transaction_type": transaction_type,
        "source_audit_id": source_audit_id,
        "enqueue_mode": enqueue_mode or ENQUEUE_MODE_MANUAL_REVIEW_QUEUE,
        "lines": lines,
        "validation": validation,
        "review_required": True,
    }
    entry["review_plan_path"] = write_review_step_file(
        tier="tier_1",
        actor=actor,
        action=f"queue-{entry['queue_id']}",
        summary=f"Queue QuickBooks Desktop draft {entry['queue_id']} for human approval.",
        payload={
            "queue_id": entry["queue_id"],
            "description": sanitized_description,
            "transaction_date": transaction_date,
            "accounting_period": accounting_period,
            "amount": round(amount, 2),
            "transaction_type": transaction_type,
            "enqueue_mode": entry["enqueue_mode"],
            "lines": lines,
            "validation": validation,
        },
    )
    insert_accounting_posting_queue_entry(entry)
    append_ai_activity_log(
        tier="tier_1",
        actor=actor,
        action="queue-accounting-draft",
        detail=f"Queued QuickBooks Desktop draft {entry['queue_id']} for human review. Review plan: {entry['review_plan_path']}",
    )
    audit_entry = record_hal_audit(
        actor=actor,
        mode=f"{HAL_MODE}:posting-queue",
        sanitized_question=sanitized_description,
        retrieval_ids=[source_audit_id],
        response_summary=f"Queued QuickBooks Desktop posting draft {entry['queue_id']} for human review."[:180],
    )
    entry["audit_id"] = audit_entry["audit_id"]
    return entry