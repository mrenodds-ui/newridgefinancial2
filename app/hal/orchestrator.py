from __future__ import annotations

import difflib
import json
import logging
import os
import re
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
    get_model_routing_snapshot,
    load_local_model_profile_config,
    require_lane_runtime,
    resolve_lane_profile,
)
from app.evaluation.client import get_ollama_runtime_status, load_json_file, run_structured_output_workflow
from app.services import fetch_softdent_dashboard_aggregate, list_local_accounting_documents, run_ci_gates, run_rebuild_receipt, run_refresh_and_verify, run_smoke_tests
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
DEFAULT_OLLAMA_BASE_URL = get_frontend_base_url()
LOCAL_MODEL_PROFILE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "evals" / "local_model_profiles.json"
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
        "label": "Primary response",
        "tone": "direct and grounded",
        "style_notes": [
            "Lead with the answer.",
            "Use verified facts before interpretation.",
            "Keep safety language outside the main answer when the UI can carry it.",
        ],
    },
    "second_opinion": {
        "lane": "second_opinion",
        "label": "Second opinion",
        "tone": "slower and more evaluative",
        "style_notes": [
            "Add one extra verification angle when useful.",
            "Call out tradeoffs and uncertainty.",
            "Stay practical instead of verbose.",
        ],
    },
    "patient_workflow": {
        "lane": "patient_workflow",
        "label": "Patient workflow",
        "tone": "careful and case-focused",
        "style_notes": [
            "Stay specific to the matched patient context.",
            "Use calm clinical-administrative wording.",
            "Keep governance text separate from the patient narrative when possible.",
        ],
    },
    "policy": {
        "lane": "policy",
        "label": "Policy guidance",
        "tone": "measured and review-oriented",
        "style_notes": [
            "Frame the answer as draft guidance.",
            "Ground the answer in approved citations.",
            "Make the need for review explicit without sounding defensive.",
        ],
    },
}


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
            _governance_note("Patient identifiers", "Raw identifiers stay inside the reviewed local patient tool and the audit trail stores the sanitized request."),
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
    runtime_status = get_ollama_runtime_status(base_url, timeout_seconds=5)
    return {
        **runtime_status,
        "lane": lane,
        "model": model,
        "api_reachable": bool(runtime_status.get("api_reachable")),
    }


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


def _build_context_excerpt_summary(items: list[dict[str, object]], *, limit: int = 2) -> str:
    prioritized_items = sorted(
        items,
        key=lambda item: 0 if str(item.get("category") or "") == "documentation" else 1,
    )
    excerpts: list[str] = []
    seen: set[str] = set()
    for item in prioritized_items:
        if str(item.get("category") or "") == "softdent_aggregate":
            continue
        excerpt = str(item.get("excerpt") or "").strip()
        if not excerpt or excerpt.startswith("#") or excerpt in seen:
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


def _is_operating_picture_request(question: str) -> bool:
    lowered = question.lower()
    return "operating picture" in lowered or "what can you do" in lowered or "capabilities" in lowered or (
        "hal" in lowered and any(keyword in lowered for keyword in ("status", "runtime", "health", "model", "routing"))
    )


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
        )
    )


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


def answer_hal_question(
    *,
    question: str,
    actor: str,
    summary: dict[str, object] | None = None,
    session_id: str | None = None,
) -> dict[str, object]:
    del summary
    state = _get_conversation_state(actor, session_id)
    patient_context = get_controlled_patient_context(question)
    if (not bool(patient_context.get("matched"))) and _is_patient_follow_up_question(question):
        last_patient_name = str(state.get("last_patient_name") or "").strip()
        if last_patient_name:
            patient_context = get_controlled_patient_context(f"{question} Patient {last_patient_name}")
    sanitized = sanitize_hal_text(question)
    sanitized_question = str(sanitized["sanitized_text"])
    retrieved_context = retrieve_relevant_context(sanitized_question)
    live_context = get_live_financial_context(sanitized_question)
    hardware_context = compile_hardware_snippets(sanitized_question)
    hardware_review_actions = _build_hardware_review_actions(sanitized_question)
    softdent_aggregate_context = compile_softdent_aggregate_snippets(sanitized_question)
    live_report_context = compile_live_report_snippets(sanitized_question)
    combined_context = [*patient_context["snippets"], *live_context, *hardware_context, *softdent_aggregate_context, *live_report_context, *retrieved_context]
    context_titles = ", ".join(_get_context_title(item) for item in combined_context)
    operating_picture = _build_hal_operating_picture(get_financial_source_status())
    lowered_question = question.lower()
    if patient_context["matched"]:
        patient_summary = _build_patient_context_summary(patient_context)
        if _is_patient_follow_up_question(question) and ("follow-up plan" in lowered_question or "follow up plan" in lowered_question):
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
        context_summary = _build_context_excerpt_summary(combined_context)
        hardware_summary = _build_hardware_answer_summary(hardware_context)
        softdent_summary = _build_softdent_answer_summary(softdent_aggregate_context)
        report_summary = _build_report_answer_summary(live_report_context)
        answer_parts: list[str] = []
        concise_answer_frame = _should_use_concise_answer_frame(question)
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
        if include_operating_picture and not concise_answer_frame:
            answer_parts.append(
                "I can use sanitized financial summaries, KPI context, approved SoftDent aggregate snapshots, sanitized SoftDent claims or clinical-note exports when available, and approved QuickBooks read-only summaries only."
            )
            answer_parts.append(
                "Priority routing applies: Tier 1 critical actions stay proposal-only until a human explicitly confirms them; Tier 2 read-and-analyze work stays read-only and must raise [ALERT] on mismatches; Tier 3 assistance stays concise and fast."
            )
        if hardware_summary:
            answer_parts.append(f"Verified hardware metrics: {hardware_summary}")
        if softdent_summary:
            answer_parts.append(f"Verified SoftDent metrics: {softdent_summary}")
        if report_summary:
            answer_parts.append(f"Verified report metrics: {report_summary}")
        if hardware_review_actions:
            answer_parts.append("Requested hardware changes require human confirmation before any device command is sent.")
        if concise_answer_frame:
            if context_titles:
                answer_parts.append(f"Supporting context: {context_titles}.")
        else:
            answer_parts.append(f"Relevant context: {context_titles}.")
            if context_summary:
                answer_parts.append(f"Key approved guidance: {context_summary}")
            answer_parts.append(
                "If you need patient-specific action, use a reviewed read-only backend tool rather than sending raw identifiers to the assistant. HAL cannot run arbitrary SQL, expose raw patient records, or claim runtime or model changes that the backend did not verify."
            )
        answer = " ".join(part.strip() for part in answer_parts if part and part.strip())
        voice_profile = _voice_profile("primary")
        governance_notes = _build_governance_notes(review_actions_present=bool(hardware_review_actions))
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
        ] + (["raw identifiers processed only in local patient tool"] if patient_context["matched"] else []),
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "review_actions": hardware_review_actions,
        "voice_profile": voice_profile,
        "governance_notes": governance_notes,
    }


def answer_hal_second_opinion_question(
    *,
    question: str,
    actor: str,
    summary: dict[str, object] | None = None,
    session_id: str | None = None,
) -> dict[str, object]:
    payload = answer_hal_question(
        question=question,
        actor=actor,
        summary=summary,
        session_id=session_id,
    )
    return {
        **payload,
        "mode": f"{HAL_MODE}:second-opinion",
        "voice_profile": _voice_profile("second_opinion"),
    }


def answer_insurance_narrative_request(*, question: str, actor: str) -> dict[str, object]:
    patient_context = get_controlled_patient_context(question)
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
            "raw identifiers processed only in local patient tool",
            "sanitized audit trail",
            "review before submission",
        ],
        "audit_id": audit_entry["audit_id"],
        "access_policy": get_hal_access_policy(),
        "voice_profile": _voice_profile("patient_workflow"),
        "governance_notes": _build_governance_notes(patient_context_used=bool(patient_context["matched"])),
    }


def answer_patient_dossier_request(*, question: str, actor: str) -> dict[str, object]:
    patient_context = get_controlled_patient_context(question)
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
            "raw identifiers processed only in local patient tool",
            "sanitized audit trail",
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