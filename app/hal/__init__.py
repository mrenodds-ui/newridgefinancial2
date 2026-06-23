from importlib import import_module


_EXPORTS: dict[str, tuple[str, str]] = {
    "approve_hal_chart_plan": (".charting", "approve_hal_chart_plan"),
    "answer_document_rag_question": (".document_rag", "answer_document_rag_question"),
    "create_hal_chart_plan": (".charting", "create_hal_chart_plan"),
    "ingest_document_rag_upload": (".document_rag", "ingest_document_rag_upload"),
    "list_hal_chart_plans": (".charting", "list_hal_chart_plans"),
    "list_document_rag_documents": (".document_rag", "list_document_rag_documents"),
    "advance_hal_autonomy_run": (".orchestrator", "advance_hal_autonomy_run"),
    "answer_accounting_policy_question": (".orchestrator", "answer_accounting_policy_question"),
    "answer_hal_question": (".orchestrator", "answer_hal_question"),
    "answer_hal_second_opinion_question": (".orchestrator", "answer_hal_second_opinion_question"),
    "answer_insurance_narrative_request": (".orchestrator", "answer_insurance_narrative_request"),
    "answer_patient_dossier_request": (".orchestrator", "answer_patient_dossier_request"),
    "command_registry": (".orchestrator", "command_registry"),
    "create_hal_autonomy_run": (".orchestrator", "create_hal_autonomy_run"),
    "draft_accounting_journal_entry": (".orchestrator", "draft_accounting_journal_entry"),
    "get_accounting_posting_queue_summary": (".orchestrator", "get_accounting_posting_queue_summary"),
    "get_hal_access_policy": (".orchestrator", "get_hal_access_policy"),
    "get_hal_autonomy_profile": (".orchestrator", "get_hal_autonomy_profile"),
    "get_hal_autonomy_run_status": (".orchestrator", "get_hal_autonomy_run_status"),
    "get_hal_index_status": (".orchestrator", "get_hal_index_status"),
    "get_hal_shell_commands": (".orchestrator", "get_hal_shell_commands"),
    "get_hal_phases": (".orchestrator", "get_hal_phases"),
    "get_recent_hal_audits": (".audit", "get_recent_hal_audits"),
    "list_hal_autonomy_runs": (".orchestrator", "list_hal_autonomy_runs"),
    "list_accounting_posting_queue": (".orchestrator", "list_accounting_posting_queue"),
    "list_recent_accounting_posting_queue_activity": (".orchestrator", "list_recent_accounting_posting_queue_activity"),
    "list_hal_audit_events": (".orchestrator", "list_hal_audit_events"),
    "queue_accounting_posting_draft": (".orchestrator", "queue_accounting_posting_draft"),
    "review_accounting_posting_queue_entry": (".orchestrator", "review_accounting_posting_queue_entry"),
    "refresh_local_hal_index": (".orchestrator", "refresh_local_hal_index"),
}

__all__ = [
    "approve_hal_chart_plan",
    "answer_document_rag_question",
    "create_hal_chart_plan",
    "ingest_document_rag_upload",
    "list_hal_chart_plans",
    "list_document_rag_documents",
    "advance_hal_autonomy_run",
    "answer_accounting_policy_question",
    "answer_hal_question",
    "answer_hal_second_opinion_question",
    "answer_insurance_narrative_request",
    "answer_patient_dossier_request",
    "command_registry",
    "create_hal_autonomy_run",
    "draft_accounting_journal_entry",
    "get_accounting_posting_queue_summary",
    "get_hal_access_policy",
    "get_hal_autonomy_profile",
    "get_hal_autonomy_run_status",
    "get_hal_index_status",
    "get_hal_shell_commands",
    "get_hal_phases",
    "get_recent_hal_audits",
    "list_hal_autonomy_runs",
    "list_accounting_posting_queue",
    "list_recent_accounting_posting_queue_activity",
    "list_hal_audit_events",
    "queue_accounting_posting_draft",
    "review_accounting_posting_queue_entry",
    "refresh_local_hal_index",
]


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value