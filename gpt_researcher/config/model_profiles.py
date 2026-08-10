"""Whitelisted, request-scoped model profiles."""

from copy import deepcopy
from typing import Literal


ModelProfileName = Literal["simple", "deep", "baseline"]

MODEL_PROFILE_OVERRIDES: dict[ModelProfileName, dict[str, str]] = {
    "simple": {
        "FAST_LLM": "dashscope:qwen-plus",
        "SMART_LLM": "dashscope:qwen-plus",
        "STRATEGIC_LLM": "dashscope:qwen-plus",
    },
    "deep": {
        "FAST_LLM": "dashscope:qwen-plus",
        "SMART_LLM": "dashscope:qwen3.7-max",
        "STRATEGIC_LLM": "dashscope:qwen3.7-max",
    },
    "baseline": {
        "FAST_LLM": "dashscope:qwen-plus",
        "SMART_LLM": "dashscope:qwen-plus",
        "STRATEGIC_LLM": "dashscope:qwen-plus",
    },
}


def resolve_model_profile(
    report_type: str,
    requested: str | None,
) -> tuple[ModelProfileName, dict[str, str]]:
    """Resolve a report type to an allowed model profile."""
    expected = "deep" if report_type == "deep" else "simple"
    profile = requested or expected

    if profile == "baseline":
        return "baseline", deepcopy(MODEL_PROFILE_OVERRIDES["baseline"])
    if profile != expected or profile not in MODEL_PROFILE_OVERRIDES:
        raise ValueError(f"Unsupported model profile: {profile}")

    return profile, deepcopy(MODEL_PROFILE_OVERRIDES[profile])
