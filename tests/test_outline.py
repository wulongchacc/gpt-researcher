import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]


def _load_outline_module():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    skills_package = types.ModuleType("gpt_researcher.skills")
    skills_package.__path__ = [str(ROOT / "gpt_researcher" / "skills")]
    utils_package = types.ModuleType("gpt_researcher.utils")
    utils_package.__path__ = [str(ROOT / "gpt_researcher" / "utils")]
    llm_module = types.ModuleType("gpt_researcher.utils.llm")
    llm_module.create_chat_completion = AsyncMock()

    sys.modules.pop("gpt_researcher.skills.outline", None)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.skills": skills_package,
            "gpt_researcher.utils": utils_package,
            "gpt_researcher.utils.llm": llm_module,
        },
    ):
        try:
            return importlib.import_module("gpt_researcher.skills.outline")
        except ModuleNotFoundError as exc:
            raise AssertionError("outline feature module is not implemented") from exc


def _load_app_module():
    class FakeFastAPI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def add_middleware(self, *args, **kwargs):
            return None

        def mount(self, *args, **kwargs):
            return None

        def _route(self, *args, **kwargs):
            return lambda function: function

        get = _route
        post = _route
        put = _route
        delete = _route
        websocket = _route

    class FakeHTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class FakeResponse:
        def __init__(self, content=None, **kwargs):
            self.content = content
            self.headers = {}

    fastapi_module = types.ModuleType("fastapi")
    fastapi_module.FastAPI = FakeFastAPI
    fastapi_module.Request = type("Request", (), {})
    fastapi_module.WebSocket = type("WebSocket", (), {})
    fastapi_module.WebSocketDisconnect = type("WebSocketDisconnect", (Exception,), {})
    fastapi_module.File = lambda *args, **kwargs: None
    fastapi_module.UploadFile = type("UploadFile", (), {})
    fastapi_module.BackgroundTasks = type("BackgroundTasks", (), {})
    fastapi_module.HTTPException = FakeHTTPException

    cors_module = types.ModuleType("fastapi.middleware.cors")
    cors_module.CORSMiddleware = type("CORSMiddleware", (), {})
    staticfiles_module = types.ModuleType("fastapi.staticfiles")
    staticfiles_module.StaticFiles = type(
        "StaticFiles",
        (),
        {"__init__": lambda self, *args, **kwargs: None},
    )
    responses_module = types.ModuleType("fastapi.responses")
    responses_module.FileResponse = FakeResponse
    responses_module.JSONResponse = FakeResponse
    responses_module.HTMLResponse = FakeResponse

    websocket_module = types.ModuleType("server.websocket_manager")
    websocket_module.WebSocketManager = type("WebSocketManager", (), {})
    websocket_module.run_agent = AsyncMock()
    server_utils_module = types.ModuleType("server.server_utils")
    for name in (
        "get_config_dict",
        "sanitize_filename",
        "update_environment_variables",
        "handle_file_upload",
        "handle_file_deletion",
        "execute_multi_agents",
        "handle_websocket_communication",
    ):
        setattr(server_utils_module, name, Mock())
    discovery_module = types.ModuleType("server.agent_discovery")
    discovery_module.build_agent_discovery_document = Mock(return_value={})
    report_store_module = types.ModuleType("server.report_store")
    report_store_module.ReportStore = type(
        "ReportStore",
        (),
        {"__init__": lambda self, *args, **kwargs: None},
    )

    language_module = types.ModuleType("gpt_researcher.utils.language")
    language_module.normalize_report_language = lambda value: value
    enum_module = types.ModuleType("gpt_researcher.utils.enum")
    enum_module.Tone = type("Tone", (), {})
    config_module = types.ModuleType("gpt_researcher.config")
    config_module.Config = type("Config", (), {})
    profile_module = types.ModuleType("gpt_researcher.config.model_profiles")
    profile_module.resolve_model_profile = Mock()

    outline_module = _load_outline_module()
    utils_module = types.ModuleType("utils")
    utils_module.write_md_to_word = AsyncMock()
    utils_module.write_md_to_pdf = AsyncMock()
    chat_module = types.ModuleType("chat.chat")
    chat_module.ChatAgentWithMemory = type("ChatAgentWithMemory", (), {})

    module_name = "backend.server.app"
    module_path = ROOT / "backend" / "server" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {
            "fastapi": fastapi_module,
            "fastapi.middleware.cors": cors_module,
            "fastapi.staticfiles": staticfiles_module,
            "fastapi.responses": responses_module,
            "server.websocket_manager": websocket_module,
            "server.server_utils": server_utils_module,
            "server.agent_discovery": discovery_module,
            "server.report_store": report_store_module,
            "gpt_researcher.utils.language": language_module,
            "gpt_researcher.utils.enum": enum_module,
            "gpt_researcher.config": config_module,
            "gpt_researcher.config.model_profiles": profile_module,
            "gpt_researcher.skills.outline": outline_module,
            "utils": utils_module,
            "chat.chat": chat_module,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


def _raw_outline(*sections):
    import json

    return json.dumps({"sections": list(sections)}, ensure_ascii=False)


def _section(title, description="研究范围"):
    return {"title": title, "description": description}


class OutlineParserTests(unittest.TestCase):
    def test_valid_json_returns_stable_section_ids(self):
        module = _load_outline_module()

        result = module.parse_outline_response(
            _raw_outline(
                _section("行业背景"),
                _section("应用现状"),
                _section("未来趋势"),
            )
        )

        self.assertEqual(
            [section.id for section in result],
            ["section-1", "section-2", "section-3"],
        )
        self.assertEqual(result[0].title, "行业背景")
        self.assertEqual(result[0].description, "研究范围")

    def test_markdown_json_fence_is_accepted(self):
        module = _load_outline_module()
        raw = _raw_outline(
            _section("行业背景"),
            _section("应用现状"),
            _section("未来趋势"),
        )

        result = module.parse_outline_response(f"```json\n{raw}\n```")

        self.assertEqual(len(result), 3)

    def test_blank_title_is_rejected(self):
        module = _load_outline_module()

        with self.assertRaises(module.OutlineParseError):
            module.parse_outline_response(
                _raw_outline(
                    _section("行业背景"),
                    _section("   "),
                    _section("未来趋势"),
                )
            )

    def test_duplicate_titles_are_removed_case_insensitively(self):
        module = _load_outline_module()

        result = module.parse_outline_response(
            _raw_outline(
                _section("Industry Background"),
                _section("industry background"),
                _section("Current Applications"),
                _section("Future Trends"),
            )
        )

        self.assertEqual(
            [section.title for section in result],
            ["Industry Background", "Current Applications", "Future Trends"],
        )

    def test_more_than_five_sections_are_truncated(self):
        module = _load_outline_module()

        result = module.parse_outline_response(
            _raw_outline(*[_section(f"Section {index}") for index in range(1, 7)])
        )

        self.assertEqual(len(result), 5)
        self.assertEqual(result[-1].title, "Section 5")

    def test_fewer_than_three_sections_are_rejected(self):
        module = _load_outline_module()

        with self.assertRaises(module.OutlineParseError):
            module.parse_outline_response(
                _raw_outline(_section("行业背景"), _section("未来趋势"))
            )


class OutlinePlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_uses_strategic_model_and_requested_language(self):
        module = _load_outline_module()
        completion = AsyncMock(
            return_value=_raw_outline(
                _section("行业背景"),
                _section("应用现状"),
                _section("未来趋势"),
            )
        )
        module.create_chat_completion = completion
        config = SimpleNamespace(
            strategic_llm_provider="dashscope",
            strategic_llm_model="qwen3.7-max",
            reasoning_effort="high",
            strategic_token_limit=2000,
            llm_kwargs={},
        )

        planner = module.OutlinePlanner(config)
        result = await planner.generate(
            task="研究人工智能对软件开发岗位的影响",
            language="Chinese (Simplified)",
        )

        self.assertEqual(len(result), 3)
        call = completion.await_args.kwargs
        self.assertEqual(call["llm_provider"], "dashscope")
        self.assertEqual(call["model"], "qwen3.7-max")
        prompt = "\n".join(message["content"] for message in call["messages"])
        self.assertIn("Chinese (Simplified)", prompt)
        self.assertIn("研究人工智能对软件开发岗位的影响", prompt)

    async def test_generate_rejects_blank_task_without_calling_model(self):
        module = _load_outline_module()
        completion = AsyncMock()
        module.create_chat_completion = completion
        planner = module.OutlinePlanner(SimpleNamespace())

        with self.assertRaises(ValueError):
            await planner.generate(task="   ", language="Chinese (Simplified)")

        completion.assert_not_awaited()


class OutlineApiTests(unittest.IsolatedAsyncioTestCase):
    def _require_api(self, module):
        self.assertTrue(hasattr(module, "OutlineRequest"))
        self.assertTrue(hasattr(module, "generate_outline"))

    async def test_endpoint_uses_requested_simple_profile(self):
        module = _load_app_module()
        self._require_api(module)
        config = SimpleNamespace(apply_runtime_overrides=Mock())
        module.Config = Mock(return_value=config)
        module.resolve_model_profile = Mock(
            return_value=("simple", {"STRATEGIC_LLM": "dashscope:qwen-plus"})
        )
        planner = SimpleNamespace(
            generate=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="section-1",
                        title="行业背景",
                        description="研究范围",
                    ),
                    SimpleNamespace(
                        id="section-2",
                        title="应用现状",
                        description="研究范围",
                    ),
                    SimpleNamespace(
                        id="section-3",
                        title="未来趋势",
                        description="研究范围",
                    ),
                ]
            )
        )
        module.OutlinePlanner = Mock(return_value=planner)

        response = await module.generate_outline(
            module.OutlineRequest(
                task="研究人工智能对软件开发岗位的影响",
                language="Chinese (Simplified)",
                report_type="research_report",
                model_profile="simple",
            )
        )

        module.resolve_model_profile.assert_called_once_with(
            "research_report", "simple"
        )
        config.apply_runtime_overrides.assert_called_once_with(
            {"STRATEGIC_LLM": "dashscope:qwen-plus"}
        )
        planner.generate.assert_awaited_once_with(
            task="研究人工智能对软件开发岗位的影响",
            language="Chinese (Simplified)",
        )
        self.assertEqual(response.model_profile, "simple")
        self.assertEqual(response.sections[0]["id"], "section-1")

    async def test_endpoint_uses_requested_deep_profile_and_returns_sections(self):
        module = _load_app_module()
        self._require_api(module)
        config = SimpleNamespace(apply_runtime_overrides=Mock())
        module.Config = Mock(return_value=config)
        module.resolve_model_profile = Mock(
            return_value=("deep", {"STRATEGIC_LLM": "dashscope:qwen3.7-max"})
        )
        planner = SimpleNamespace(
            generate=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="section-1",
                        title="行业背景",
                        description="研究范围",
                    ),
                    SimpleNamespace(
                        id="section-2",
                        title="应用现状",
                        description="研究范围",
                    ),
                    SimpleNamespace(
                        id="section-3",
                        title="未来趋势",
                        description="研究范围",
                    ),
                ]
            )
        )
        module.OutlinePlanner = Mock(return_value=planner)

        response = await module.generate_outline(
            module.OutlineRequest(
                task="研究人工智能对软件开发岗位的影响",
                language="Chinese (Simplified)",
                report_type="deep",
                model_profile="deep",
            )
        )

        module.resolve_model_profile.assert_called_once_with("deep", "deep")
        config.apply_runtime_overrides.assert_called_once_with(
            {"STRATEGIC_LLM": "dashscope:qwen3.7-max"}
        )
        planner.generate.assert_awaited_once_with(
            task="研究人工智能对软件开发岗位的影响",
            language="Chinese (Simplified)",
        )
        self.assertEqual(response.model_profile, "deep")
        self.assertEqual(response.sections[0]["id"], "section-1")

    def test_mismatched_report_type_and_profile_is_rejected(self):
        module = _load_app_module()
        self._require_api(module)

        with self.assertRaises(ValidationError):
            module.OutlineRequest(
                task="研究主题",
                report_type="research_report",
                model_profile="deep",
            )

    def test_blank_task_is_rejected_by_request_model(self):
        module = _load_app_module()
        self._require_api(module)

        with self.assertRaises(ValidationError):
            module.OutlineRequest(
                task="   ",
                report_type="deep",
                model_profile="deep",
            )

    async def test_planner_failure_is_returned_as_http_502(self):
        module = _load_app_module()
        self._require_api(module)
        module.Config = Mock(return_value=SimpleNamespace(apply_runtime_overrides=Mock()))
        module.resolve_model_profile = Mock(return_value=("deep", {}))
        module.OutlinePlanner = Mock(
            return_value=SimpleNamespace(
                generate=AsyncMock(side_effect=module.OutlineParseError("invalid outline"))
            )
        )

        with self.assertLogs(module.logger, level="WARNING"):
            with self.assertRaises(module.HTTPException) as raised:
                await module.generate_outline(
                    module.OutlineRequest(
                        task="研究问题",
                        report_type="deep",
                        model_profile="deep",
                    )
                )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("invalid outline", raised.exception.detail)

    async def test_model_failure_is_returned_as_http_502(self):
        module = _load_app_module()
        self._require_api(module)
        module.Config = Mock(return_value=SimpleNamespace(apply_runtime_overrides=Mock()))
        module.resolve_model_profile = Mock(return_value=("deep", {}))
        module.OutlinePlanner = Mock(
            return_value=SimpleNamespace(
                generate=AsyncMock(side_effect=RuntimeError("dashscope unavailable"))
            )
        )

        with self.assertLogs(module.logger, level="WARNING"):
            with self.assertRaises(module.HTTPException) as raised:
                await module.generate_outline(
                    module.OutlineRequest(
                        task="研究问题",
                        report_type="deep",
                        model_profile="deep",
                    )
                )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("dashscope unavailable", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
