from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4

from local_ai_finance import main as local_ai_finance

from .orchestrator import get_hal_access_policy
from .safety import append_ai_activity_log, get_ai_workspace_path, read_review_step_file, update_review_step_file, workspace_relative_path, write_review_step_file


def _slugify(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:64] or fallback


def _make_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def create_hal_chart_plan(
    *,
    question: str,
    actor: str,
    profile_alias: str = local_ai_finance.DEFAULT_PROFILE_ALIAS,
    timeout_seconds: int = 90,
    processing_limit: int = 12,
) -> dict[str, object]:
    audit_id = f"hal-chart-{uuid4().hex[:12]}"
    payload = local_ai_finance.generate_chart_request(
        user_request=question,
        filename=None,
        profile_alias=profile_alias,
        timeout_seconds=timeout_seconds,
        processing_limit=processing_limit,
    )
    payload = local_ai_finance.apply_chart_request_guardrails(payload)
    local_ai_finance.validate_chart_payload(payload)

    chart_title = str(payload.get("chart_config", {}).get("title") or "HAL chart")
    chart_label = _slugify(chart_title, fallback="hal-chart")
    request_filename = local_ai_finance.build_dated_chart_filename(
        label=f"{chart_label}-generated-chart-request",
        suffix=".json",
    )
    output_filename = local_ai_finance.build_dated_chart_filename(
        label=chart_label,
        suffix=".png",
    )

    workspace = get_ai_workspace_path()
    request_path = _make_unique_path(workspace / request_filename)
    output_path = _make_unique_path(workspace / output_filename)
    request_path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")

    preview_summary = local_ai_finance.build_chart_preview_summary(payload, output_filename=output_path.name)
    review_plan_path = write_review_step_file(
        tier="tier_1",
        actor=actor,
        action="hal_chart_render",
        summary=preview_summary,
        payload={
            "audit_id": audit_id,
            "question": question,
            "request_file_path": str(request_path),
            "planned_output_path": str(output_path),
            "chart_request": payload,
        },
    )
    append_ai_activity_log(
        tier="tier_2",
        actor=actor,
        action="hal_chart_plan",
        detail=f"Generated staged HAL chart request {request_path.name}; planned output {output_path.name}; review plan {Path(review_plan_path).name}.",
    )

    return {
        "mode": "local-rag-phase-1",
        "status": "pending_human_review",
        "question": question,
        "request_json": payload,
        "request_file_path": str(request_path),
        "planned_output_path": str(output_path),
        "review_plan_path": str(review_plan_path),
        "preview_summary": preview_summary,
        "flag_for_review": bool(payload.get("flag_for_review")),
        "review_reason": str(payload.get("review_reason") or "") or None,
        "alert_reason": str(payload.get("alert_reason") or "") or None,
        "guardrails": [
            "structured chart JSON only",
            "pending human review before PNG render",
            "sandboxed artifact staging inside AI_Workspace",
        ],
        "audit_id": audit_id,
        "access_policy": get_hal_access_policy(),
    }


def list_hal_chart_plans(*, limit: int = 20, status: str | None = None) -> dict[str, object]:
    review_dir = get_ai_workspace_path() / "review_plans"
    review_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, object]] = []
    for file_path in sorted(review_dir.glob("*.json"), reverse=True):
        try:
            _, document = read_review_step_file(file_path)
        except (ValueError, json.JSONDecodeError, FileNotFoundError):
            continue
        if str(document.get("action") or "") != "hal_chart_render":
            continue
        document_status = str(document.get("status") or "pending_human_approval")
        if status and document_status != status:
            continue
        payload = document.get("payload") if isinstance(document.get("payload"), dict) else {}
        chart_request = payload.get("chart_request") if isinstance(payload, dict) and isinstance(payload.get("chart_request"), dict) else {}
        chart_config = chart_request.get("chart_config") if isinstance(chart_request, dict) and isinstance(chart_request.get("chart_config"), dict) else {}
        planned_output_path = str(payload.get("planned_output_path") or "") if isinstance(payload, dict) else ""
        rendered_output_path = str(document.get("rendered_output_path") or "") or None
        items.append(
            {
                "review_plan_path": str(file_path),
                "created_at_utc": str(document.get("created_at_utc") or ""),
                "status": document_status,
                "question": str(payload.get("question") or "") if isinstance(payload, dict) else "",
                "title": str(chart_config.get("title") or "HAL chart"),
                "chart_type": str(chart_config.get("chart_type") or "bar"),
                "planned_output_path": str(planned_output_path) if planned_output_path else "",
                "rendered_output_path": str(rendered_output_path) if rendered_output_path else None,
                "audit_id": str(payload.get("audit_id") or "") if isinstance(payload, dict) else "",
            }
        )
        if len(items) >= limit:
            break
    return {
        "count": len(items),
        "limit": limit,
        "status": status,
        "items": items,
    }


def _render_chart_payload_to_path(payload: dict[str, object], output_path: Path) -> None:
    chart_config = payload["chart_config"]
    chart_data = payload["chart_data"]

    image = local_ai_finance.Image.new("RGB", (1200, 720), color=(248, 249, 250))
    draw = local_ai_finance.ImageDraw.Draw(image)
    draw.text((40, 24), str(chart_config["title"]), fill=(20, 24, 28))
    draw.text((40, 58), f"X: {chart_config['x_axis_label']}", fill=(80, 86, 94))
    draw.text((300, 58), f"Y: {chart_config['y_axis_label']}", fill=(80, 86, 94))

    chart_type = str(chart_config["chart_type"]).lower()
    if chart_type == "pie":
        chart_box = (60, 110, 560, 610)
        local_ai_finance._draw_pie_chart(draw, chart_box, chart_data, chart_config)
    elif chart_type == "line":
        chart_box = (80, 130, 1080, 560)
        draw.line((80, 560, 1080, 560), fill=(120, 128, 136), width=2)
        draw.line((80, 130, 80, 560), fill=(120, 128, 136), width=2)
        local_ai_finance._draw_line_chart(draw, chart_box, chart_data, chart_config)
    else:
        chart_box = (80, 130, 1080, 560)
        draw.line((80, 560, 1080, 560), fill=(120, 128, 136), width=2)
        draw.line((80, 130, 80, 560), fill=(120, 128, 136), width=2)
        local_ai_finance._draw_bar_chart(draw, chart_box, chart_data, chart_config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def approve_hal_chart_plan(*, review_plan_path: str, actor: str) -> dict[str, object]:
    resolved_review_plan_path, document = read_review_step_file(review_plan_path)
    if str(document.get("action") or "") != "hal_chart_render":
        raise ValueError("Review plan action is not a HAL chart render request.")
    if str(document.get("status") or "") != "pending_human_approval":
        raise ValueError("Review plan is no longer pending human approval.")

    payload = document.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Review plan payload is missing.")

    chart_request = payload.get("chart_request")
    if not isinstance(chart_request, dict):
        raise ValueError("Chart request payload is missing from the review plan.")

    validated_payload = local_ai_finance.apply_chart_request_guardrails(chart_request)
    local_ai_finance.validate_chart_payload(validated_payload)

    planned_output_path = payload.get("planned_output_path")
    if not isinstance(planned_output_path, str) or not planned_output_path.strip():
        raise ValueError("Review plan is missing the planned output path.")

    output_path = _make_unique_path(local_ai_finance.Path(planned_output_path))
    _render_chart_payload_to_path(validated_payload, output_path)

    update_review_step_file(
        review_plan_path=resolved_review_plan_path,
        status="approved_and_rendered",
        actor=actor,
        extra_fields={
            "rendered_output_path": str(output_path),
        },
    )
    append_ai_activity_log(
        tier="tier_1",
        actor=actor,
        action="hal_chart_render_approved",
        detail=f"Rendered HAL chart from {resolved_review_plan_path.name} to {output_path.name}.",
    )

    return {
        "mode": "local-rag-phase-1",
        "status": "approved_and_rendered",
        "review_plan_path": str(resolved_review_plan_path),
        "request_json": validated_payload,
        "rendered_output_path": str(output_path),
        "flag_for_review": bool(validated_payload.get("flag_for_review")),
        "review_reason": str(validated_payload.get("review_reason") or "") or None,
        "alert_reason": str(validated_payload.get("alert_reason") or "") or None,
        "guardrails": [
            "human approval recorded before PNG render",
            "sandboxed artifact write inside AI_Workspace",
            "structured chart JSON validated before render",
        ],
        "audit_id": str(payload.get("audit_id") or ""),
        "access_policy": get_hal_access_policy(),
    }