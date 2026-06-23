import json
import subprocess
import sys

import pytest

import app.quickbooks_sdk_runner as quickbooks_sdk_runner
import app.services as services


def test_build_quickbooks_sdk_request_without_period_retains_legacy_contract():
    xml_out = services._build_quickbooks_sdk_request("revenue")

    assert "<GeneralSummaryReportType>ProfitAndLossStandard</GeneralSummaryReportType>" in xml_out
    assert "<FromReportDate>" not in xml_out
    assert "<ToReportDate>" not in xml_out


def test_build_quickbooks_sdk_request_injects_valid_date_elements():
    xml_out = services._build_quickbooks_sdk_request(
        "revenue",
        period_dict={"start_date": "2026-05-01", "end_date": "2026-05-31"},
    )

    expected_segment = (
        "<GeneralSummaryReportType>ProfitAndLossStandard</GeneralSummaryReportType>"
        "<ReportPeriod>"
        "<FromReportDate>2026-05-01</FromReportDate>"
        "<ToReportDate>2026-05-31</ToReportDate>"
        "</ReportPeriod>"
    )
    assert expected_segment in xml_out


def test_build_quickbooks_sdk_request_injects_date_elements_for_expenses():
    xml_out = services._build_quickbooks_sdk_request(
        "expenses",
        period_dict={"start_date": "2026-05-01", "end_date": "2026-05-31"},
    )

    expected_segment = (
        "<GeneralSummaryReportType>ProfitAndLossStandard</GeneralSummaryReportType>"
        "<ReportPeriod>"
        "<FromReportDate>2026-05-01</FromReportDate>"
        "<ToReportDate>2026-05-31</ToReportDate>"
        "</ReportPeriod>"
    )
    assert expected_segment in xml_out


def test_build_quickbooks_sdk_request_strips_date_elements_for_ar_topic():
    xml_out = services._build_quickbooks_sdk_request(
        "ar",
        period_dict={"start_date": "2026-05-01", "end_date": "2026-05-31"},
    )

    assert "<GeneralSummaryReportType>ARAgingSummary</GeneralSummaryReportType>" in xml_out
    assert "<ReportPeriod><FromReportDate>2026-05-01</FromReportDate><ToReportDate>2026-05-31</ToReportDate></ReportPeriod>" in xml_out


def test_parse_quickbooks_sdk_summary_maps_ar_aging_report_rows():
    response_xml = """
    <QBXML>
      <QBXMLMsgsRs>
        <GeneralSummaryReportQueryRs statusCode="0" statusSeverity="Info" statusMessage="Status OK">
          <ReportRet>
            <ReportTitle>A/R Aging Summary</ReportTitle>
            <ReportSubtitle>As of June 16, 2026</ReportSubtitle>
            <ReportBasis>Accrual</ReportBasis>
            <NumColumns>6</NumColumns>
            <NumRows>3</NumRows>
            <DataRow>
              <ColData colID="1" value="Acme Dental" />
              <ColData colID="2" value="125.00" />
              <ColData colID="3" value="25.00" />
              <ColData colID="4" value="0.00" />
              <ColData colID="5" value="0.00" />
              <ColData colID="6" value="150.00" />
            </DataRow>
            <DataRow>
              <ColData colID="1" value="Bravo Family" />
              <ColData colID="2" value="0.00" />
              <ColData colID="3" value="0.00" />
              <ColData colID="4" value="10.00" />
              <ColData colID="5" value="5.00" />
              <ColData colID="6" value="15.00" />
            </DataRow>
            <TextRow>
              <ColData colID="1" value="Total" />
              <ColData colID="6" value="165.00" />
            </TextRow>
          </ReportRet>
        </GeneralSummaryReportQueryRs>
      </QBXMLMsgsRs>
    </QBXML>
    """

    payload = services._parse_quickbooks_sdk_summary(topic="ar", response_xml=response_xml)

    assert payload == [
        {
            "CustomerRef": "Acme Dental",
            "OutstandingAR": "150.00",
            "ReportDate": "As of June 16, 2026",
            "RefNumber": "",
        },
        {
            "CustomerRef": "Bravo Family",
            "OutstandingAR": "15.00",
            "ReportDate": "As of June 16, 2026",
            "RefNumber": "",
        },
    ]


def test_build_quickbooks_sdk_request_rejects_invalid_period_order():
    with pytest.raises(ValueError, match="end_date must be on or after start_date"):
        services._build_quickbooks_sdk_request(
            "revenue",
            period_dict={"start_date": "2026-05-31", "end_date": "2026-05-01"},
        )


def test_build_quickbooks_sdk_request_rejects_unsupported_topic():
    with pytest.raises(ValueError, match="Unsupported QuickBooks SDK topic"):
        services._build_quickbooks_sdk_request("balance_sheet")


def test_fetch_quickbooks_sdk_summary_includes_period_args_in_subprocess_command(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([{"ok": True}]), stderr="")

    monkeypatch.setattr(services.subprocess, "run", fake_run)

    payload = services.fetch_quickbooks_sdk_summary(
        "revenue",
        period_dict={"start_date": "2026-05-01", "end_date": "2026-05-31"},
    )

    assert payload == [{"ok": True}]
    assert captured["command"] == [
        sys.executable,
        "-m",
        "app.quickbooks_sdk_runner",
        "revenue",
        "2026-05-01",
        "2026-05-31",
    ]


def test_fetch_quickbooks_sdk_summary_rejects_unsupported_topic_before_subprocess(monkeypatch):
    captured = {"called": False}

    def fake_run(command, **kwargs):
        captured["called"] = True
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([{"ok": True}]), stderr="")

    monkeypatch.setattr(services.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="Unsupported QuickBooks SDK topic"):
        services.fetch_quickbooks_sdk_summary("balance_sheet")

    assert captured["called"] is False


def test_fetch_quickbooks_sdk_summary_wraps_invalid_json(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="not-json", stderr="")

    monkeypatch.setattr(services.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="invalid JSON output"):
        services.fetch_quickbooks_sdk_summary("revenue")


def test_validate_quickbooks_diagnostic_sql_rejects_overlong_query():
    overlong_sql = "SELECT " + ("x" * services.MAX_QUICKBOOKS_DIAGNOSTIC_SQL_LENGTH)

    with pytest.raises(ValueError, match="10000 characters or fewer"):
        services.validate_quickbooks_diagnostic_sql(overlong_sql)


def test_quickbooks_sdk_runner_passes_period_dict(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_fetch(topic: str, period_dict: dict[str, str] | None = None):
        captured["topic"] = topic
        captured["period_dict"] = period_dict
        return [{"ReportTitle": "Profit & Loss"}]

    monkeypatch.setattr(quickbooks_sdk_runner, "fetch_quickbooks_sdk_summary_direct", fake_fetch)
    monkeypatch.setattr(sys, "argv", ["quickbooks_sdk_runner.py", "revenue", "2026-05-01", "2026-05-31"])

    exit_code = quickbooks_sdk_runner.main()

    assert exit_code == 0
    assert captured == {
        "topic": "revenue",
        "period_dict": {"start_date": "2026-05-01", "end_date": "2026-05-31"},
    }
    assert capsys.readouterr().out.strip() == json.dumps([{"ReportTitle": "Profit & Loss"}])
