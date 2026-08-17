import importlib
import os
import sys
import types
import unittest
from enum import Enum
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _load_websocket_manager_module():
    for path in (ROOT, ROOT / "backend"):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    for module_name in (
        "backend.server.websocket_manager",
        "backend.server.multi_agent_runner",
        "backend.server.server_utils",
        "gpt_researcher.actions",
        "gpt_researcher.utils.enum",
        "report_type",
        "backend.report_type",
        "fastapi",
    ):
        sys.modules.pop(module_name, None)

    fastapi_module = types.ModuleType("fastapi")
    fastapi_module.WebSocket = type("WebSocket", (), {})

    report_type_module = types.ModuleType("backend.report_type")
    report_type_module.BasicReport = type("BasicReport", (), {})
    report_type_module.DetailedReport = type("DetailedReport", (), {})

    enum_module = types.ModuleType("gpt_researcher.utils.enum")

    class ReportType(Enum):
        DetailedReport = "detailed_report"

    class Tone(Enum):
        Objective = "objective"

    enum_module.ReportType = ReportType
    enum_module.Tone = Tone

    actions_module = types.ModuleType("gpt_researcher.actions")
    actions_module.stream_output = lambda *args, **kwargs: None

    multi_agent_runner_module = types.ModuleType("backend.server.multi_agent_runner")

    async def run_multi_agent_task(*args, **kwargs):
        return {"report": "stub-report"}

    multi_agent_runner_module.run_multi_agent_task = run_multi_agent_task

    server_utils_module = types.ModuleType("backend.server.server_utils")
    server_utils_module.CustomLogsHandler = type("CustomLogsHandler", (), {})

    with patch.dict(
        sys.modules,
        {
            "fastapi": fastapi_module,
            "report_type": report_type_module,
            "backend.report_type": report_type_module,
            "gpt_researcher.utils.enum": enum_module,
            "gpt_researcher.actions": actions_module,
            "backend.server.multi_agent_runner": multi_agent_runner_module,
            "backend.server.server_utils": server_utils_module,
        },
    ):
        return importlib.import_module("backend.server.websocket_manager")


class WebSocketManagerTests(unittest.IsolatedAsyncioTestCase):
    def test_websocket_manager_module_imports(self):
        module = importlib.import_module("backend.server.websocket_manager")
        self.assertTrue(hasattr(module, "WebSocketManager"))

    def test_server_app_module_imports(self):
        module = importlib.import_module("backend.server.app")
        self.assertTrue(hasattr(module, "app"))

    async def test_start_streaming_reads_config_path_from_environment(self):
        websocket_manager = _load_websocket_manager_module()
        manager = websocket_manager.WebSocketManager()
        call_kwargs = {}

        async def fake_run_agent(*args, **kwargs):
            call_kwargs.update(kwargs)
            return "stub-report"

        websocket_manager.run_agent = fake_run_agent

        with patch.dict(os.environ, {"CONFIG_PATH": "custom-config"}, clear=False):
            report = await manager.start_streaming(
                task="test-task",
                report_type="research_report",
                report_source="web",
                source_urls=[],
                document_urls=[],
                tone="Objective",
                websocket=object(),
                language="Chinese (Simplified)",
                model_profile="deep",
                reliability_enabled=True,
                outline=[{"id": "section-1", "title": "范围", "description": "定义"}],
            )

        self.assertEqual(report, "stub-report")
        self.assertEqual(call_kwargs["config_path"], "custom-config")
        self.assertEqual(call_kwargs["language"], "Chinese (Simplified)")
        self.assertEqual(call_kwargs["model_profile"], "deep")
        self.assertIs(call_kwargs["reliability_enabled"], True)
        self.assertEqual(
            call_kwargs["outline"],
            [{"id": "section-1", "title": "范围", "description": "定义"}],
        )

    async def test_run_agent_passes_execution_options_to_basic_report(self):
        websocket_manager = _load_websocket_manager_module()
        captured = {}

        class FakeLogsHandler:
            def __init__(self, websocket, task):
                self.websocket = websocket
                self.task = task

        class FakeBasicReport:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self.gpt_researcher = object()

            async def run(self):
                return "stub-report"

        websocket_manager.CustomLogsHandler = FakeLogsHandler
        websocket_manager.BasicReport = FakeBasicReport

        report = await websocket_manager.run_agent(
            task="test-task",
            report_type="deep",
            report_source="web",
            source_urls=[],
            document_urls=[],
            tone=websocket_manager.Tone.Objective,
            websocket=object(),
            model_profile="deep",
            reliability_enabled=True,
            outline=[{"id": "section-1", "title": "范围", "description": "定义"}],
        )

        self.assertEqual(report, "stub-report")
        self.assertEqual(captured["model_profile"], "deep")
        self.assertIs(captured["reliability_enabled"], True)
        self.assertEqual(
            captured["outline"],
            [{"id": "section-1", "title": "范围", "description": "定义"}],
        )

    async def test_run_agent_passes_simple_outline_to_basic_report(self):
        websocket_manager = _load_websocket_manager_module()
        captured = {}

        class FakeLogsHandler:
            def __init__(self, websocket, task):
                self.websocket = websocket
                self.task = task

        class FakeBasicReport:
            def __init__(self, **kwargs):
                captured.update(kwargs)
                self.gpt_researcher = object()

            async def run(self):
                return "stub-report"

        websocket_manager.CustomLogsHandler = FakeLogsHandler
        websocket_manager.BasicReport = FakeBasicReport
        outline = [
            {"id": "section-1", "title": "现状", "description": "应用范围"}
        ]

        report = await websocket_manager.run_agent(
            task="test-task",
            report_type="research_report",
            report_source="web",
            source_urls=[],
            document_urls=[],
            tone=websocket_manager.Tone.Objective,
            websocket=object(),
            model_profile="simple",
            outline=outline,
        )

        self.assertEqual(report, "stub-report")
        self.assertEqual(captured["model_profile"], "simple")
        self.assertEqual(captured["outline"], outline)


if __name__ == "__main__":
    unittest.main()
