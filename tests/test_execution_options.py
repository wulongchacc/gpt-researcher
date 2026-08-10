import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _load_basic_report_module(captured):
    fastapi_module = types.ModuleType("fastapi")
    fastapi_module.WebSocket = type("WebSocket", (), {})

    researcher_module = types.ModuleType("gpt_researcher")

    class FakeGPTResearcher:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    researcher_module.GPTResearcher = FakeGPTResearcher

    module_name = "backend.report_type.basic_report.basic_report"
    module_path = (
        ROOT / "backend" / "report_type" / "basic_report" / "basic_report.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {
            "fastapi": fastapi_module,
            "gpt_researcher": researcher_module,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


def _load_server_utils_module():
    fastapi_module = types.ModuleType("fastapi")
    fastapi_module.HTTPException = type("HTTPException", (Exception,), {})
    responses_module = types.ModuleType("fastapi.responses")
    responses_module.JSONResponse = type("JSONResponse", (), {})
    responses_module.FileResponse = type("FileResponse", (), {})

    researcher_module = types.ModuleType("gpt_researcher")
    researcher_module.GPTResearcher = type("GPTResearcher", (), {})
    document_module = types.ModuleType("gpt_researcher.document.document")
    document_module.DocumentLoader = type("DocumentLoader", (), {})
    language_module = types.ModuleType("gpt_researcher.utils.language")
    language_module.normalize_report_language = lambda value: value

    utils_module = types.ModuleType("utils")
    utils_module.write_md_to_pdf = lambda *args, **kwargs: None
    utils_module.write_md_to_word = lambda *args, **kwargs: None
    utils_module.write_text_to_md = lambda *args, **kwargs: None

    multi_agent_module = types.ModuleType("backend.server.multi_agent_runner")
    multi_agent_module.run_multi_agent_task = lambda *args, **kwargs: None

    module_name = "backend.server.server_utils"
    module_path = ROOT / "backend" / "server" / "server_utils.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {
            "fastapi": fastapi_module,
            "fastapi.responses": responses_module,
            "gpt_researcher": researcher_module,
            "gpt_researcher.document.document": document_module,
            "gpt_researcher.utils.language": language_module,
            "utils": utils_module,
            "backend.server.multi_agent_runner": multi_agent_module,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


class ExecutionOptionsTests(unittest.TestCase):
    def test_basic_report_passes_options_to_researcher(self):
        captured = {}
        module = _load_basic_report_module(captured)
        outline = [{"id": "section-1", "title": "范围", "description": "定义"}]

        module.BasicReport(
            query="测试问题",
            query_domains=[],
            report_type="deep",
            report_source="web",
            source_urls=[],
            document_urls=[],
            tone="objective",
            config_path="default",
            websocket=object(),
            model_profile="deep",
            reliability_enabled=True,
            outline=outline,
        )

        self.assertEqual(captured["model_profile"], "deep")
        self.assertIs(captured["reliability_enabled"], True)
        self.assertEqual(captured["outline"], outline)

    def test_websocket_command_extracts_execution_options(self):
        module = _load_server_utils_module()
        outline = [{"id": "section-1", "title": "范围", "description": "定义"}]

        values = module.extract_command_data(
            {
                "task": "测试问题",
                "report_type": "deep",
                "outline": outline,
                "model_profile": "deep",
                "reliability_enabled": False,
            }
        )

        self.assertEqual(values[-3], outline)
        self.assertEqual(values[-2], "deep")
        self.assertIs(values[-1], False)


if __name__ == "__main__":
    unittest.main()
