"""Hard MoE-only policy (30B-A3B) — office program must not call other AI models."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from nr2_hal_gateway import (
    APPROVED_LOCAL_MODEL,
    call_ollama_chat,
    enforce_approved_local_model,
    resolve_lane,
)

HAL_MODELS = Path(__file__).resolve().parent / "site" / "data" / "hal-models.json"


class Hal32bOnlyPolicyTests(unittest.TestCase):
    def test_all_lanes_resolve_to_approved(self) -> None:
        for lane in ("chat8b", "reason21b", "escalate30b", "coder32b", "oss120b", "deep235b"):
            resolved = resolve_lane(lane)
            self.assertEqual(resolved["model"], APPROVED_LOCAL_MODEL)

    def test_override_foreign_model_rejected(self) -> None:
        gate = enforce_approved_local_model("gpt-oss:120b")
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["error"], "model_not_allowed")

    def test_header_foreign_model_rejected(self) -> None:
        gate = enforce_approved_local_model(None, override_header="qwen3:235b")
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["error"], "model_not_allowed")

    def test_lane_header_allowed(self) -> None:
        gate = enforce_approved_local_model(None, override_header="chat8b")
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["model"], APPROVED_LOCAL_MODEL)

    def test_approved_model_passthrough(self) -> None:
        gate = enforce_approved_local_model(APPROVED_LOCAL_MODEL)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["model"], APPROVED_LOCAL_MODEL)

    def test_call_ollama_refuses_foreign_model(self) -> None:
        out = call_ollama_chat(model="gpt-oss:120b", messages=[{"role": "user", "content": "hi"}])
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "model_not_allowed")

    def test_call_ollama_forces_approved_tag(self) -> None:
        with mock.patch("nr2_hal_gateway.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.__enter__.return_value = resp
            resp.read.return_value = json.dumps(
                {"message": {"content": "ready"}}
            ).encode("utf-8")
            urlopen.return_value = resp
            out = call_ollama_chat(model=APPROVED_LOCAL_MODEL, messages=[{"role": "user", "content": "hi"}])
            self.assertTrue(out.get("ok"))
            req = urlopen.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            self.assertEqual(body["model"], APPROVED_LOCAL_MODEL)

    def test_hal_models_inventory_is_moe_only(self) -> None:
        data = json.loads(HAL_MODELS.read_text(encoding="utf-8"))
        cfg = data["config"]
        self.assertFalse(cfg["cloudReasoning"]["enabled"])
        self.assertFalse(cfg["cloudReasoning"]["autoEnableWhenKeySet"])
        avail = data["readinessDisplay"]["availableModels"]
        self.assertEqual(set(avail), {"hal-local:30b-a3b", "qwen3:30b-a3b-instruct-2507-q4_K_M"})
        for lane in data["lanes"]:
            self.assertEqual(lane["model"], "hal-local:30b-a3b")
            self.assertEqual(lane["runtime"]["model"], "hal-local:30b-a3b")
        banned = {"oss120b", "deep235b", "helper14b", "general14b", "coder30b"}
        ids = {lane["id"] for lane in data["lanes"]}
        self.assertTrue(ids.isdisjoint(banned))


if __name__ == "__main__":
    unittest.main()
