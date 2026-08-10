import importlib
import importlib.util
import os
import sys
import types
import unittest
from enum import Enum
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _load_model_profiles_module():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    config_package = types.ModuleType("gpt_researcher.config")
    config_package.__path__ = [str(ROOT / "gpt_researcher" / "config")]

    sys.modules.pop("gpt_researcher.config.model_profiles", None)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.config": config_package,
        },
    ):
        return importlib.import_module("gpt_researcher.config.model_profiles")


def _load_config_module():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    config_package = types.ModuleType("gpt_researcher.config")
    config_package.__path__ = [str(ROOT / "gpt_researcher" / "config")]

    generic_base = types.ModuleType("gpt_researcher.llm_provider.generic.base")

    class ReasoningEfforts(Enum):
        Medium = "medium"

    generic_base.ReasoningEfforts = ReasoningEfforts

    variables_base = types.ModuleType("gpt_researcher.config.variables.base")
    variables_base.BaseConfig = type("BaseConfig", (), {"__annotations__": {}})
    variables_default = types.ModuleType("gpt_researcher.config.variables.default")
    variables_default.DEFAULT_CONFIG = {}

    module_name = "gpt_researcher.config.config"
    module_path = ROOT / "gpt_researcher" / "config" / "config.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)

    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.config": config_package,
            "gpt_researcher.llm_provider.generic.base": generic_base,
            "gpt_researcher.config.variables.base": variables_base,
            "gpt_researcher.config.variables.default": variables_default,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


class ModelProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolve_model_profile = staticmethod(
            _load_model_profiles_module().resolve_model_profile
        )

    def test_simple_profile_uses_qwen_plus_for_every_role(self):
        name, values = self.resolve_model_profile("research_report", "simple")

        self.assertEqual(name, "simple")
        self.assertEqual(values["FAST_LLM"], "dashscope:qwen-plus")
        self.assertEqual(values["SMART_LLM"], "dashscope:qwen-plus")
        self.assertEqual(values["STRATEGIC_LLM"], "dashscope:qwen-plus")

    def test_deep_profile_routes_smart_roles_to_qwen_max(self):
        name, values = self.resolve_model_profile("deep", "deep")

        self.assertEqual(name, "deep")
        self.assertEqual(values["FAST_LLM"], "dashscope:qwen-plus")
        self.assertEqual(values["SMART_LLM"], "dashscope:qwen3.7-max")
        self.assertEqual(values["STRATEGIC_LLM"], "dashscope:qwen3.7-max")

    def test_baseline_profile_keeps_deep_research_on_qwen_plus(self):
        name, values = self.resolve_model_profile("deep", "baseline")

        self.assertEqual(name, "baseline")
        self.assertEqual(values["FAST_LLM"], "dashscope:qwen-plus")
        self.assertEqual(values["SMART_LLM"], "dashscope:qwen-plus")
        self.assertEqual(values["STRATEGIC_LLM"], "dashscope:qwen-plus")

    def test_profile_is_rejected_when_it_does_not_match_report_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model profile"):
            self.resolve_model_profile("deep", "simple")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model profile"):
            self.resolve_model_profile("deep", "custom-model")


class RuntimeConfigOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Config = _load_config_module().Config

    def test_runtime_overrides_update_only_the_config_instance(self):
        config = self.Config.__new__(self.Config)
        config.fast_llm = "dashscope:old-fast"
        config.smart_llm = "dashscope:old-smart"
        config.strategic_llm = "dashscope:old-strategic"

        original_environment = {
            "FAST_LLM": os.environ.get("FAST_LLM"),
            "SMART_LLM": os.environ.get("SMART_LLM"),
            "STRATEGIC_LLM": os.environ.get("STRATEGIC_LLM"),
        }

        with patch.object(config, "_set_llm_attributes") as set_llm_attributes:
            config.apply_runtime_overrides(
                {
                    "FAST_LLM": "dashscope:qwen-plus",
                    "SMART_LLM": "dashscope:qwen3.7-max",
                    "STRATEGIC_LLM": "dashscope:qwen3.7-max",
                }
            )

        self.assertEqual(config.fast_llm, "dashscope:qwen-plus")
        self.assertEqual(config.smart_llm, "dashscope:qwen3.7-max")
        self.assertEqual(config.strategic_llm, "dashscope:qwen3.7-max")
        set_llm_attributes.assert_called_once_with()
        self.assertEqual(
            {key: os.environ.get(key) for key in original_environment},
            original_environment,
        )

    def test_runtime_overrides_reject_unknown_keys(self):
        config = self.Config.__new__(self.Config)

        with self.assertRaisesRegex(ValueError, "Unsupported runtime override"):
            config.apply_runtime_overrides({"RETRIEVER": "tavily"})


if __name__ == "__main__":
    unittest.main()
