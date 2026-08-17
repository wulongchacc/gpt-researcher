import assert from "node:assert/strict";
import test from "node:test";

import {
  buildResearchStartMessage,
  buildResearchStartPayload,
  getResearchStartAction,
  prepareResearchStart,
} from "../services/researchStart.ts";
import type {
  ChatBoxSettings,
  OutlineSection,
} from "../types/data.ts";

const settings: ChatBoxSettings = {
  report_type: "research_report",
  report_source: "web",
  tone: "Objective",
  domains: [],
  defaultReportType: "research_report",
  layoutType: "copilot",
  mcp_enabled: false,
  mcp_configs: [],
  mcp_strategy: "fast",
  language: "Chinese (Simplified)",
  confirm_outline_before_research: false,
};

const outline: OutlineSection[] = [
  { id: "section-1", title: "行业背景", description: "研究背景" },
  { id: "section-2", title: "市场现状", description: "研究市场" },
  { id: "section-3", title: "未来趋势", description: "研究趋势" },
];

test("getResearchStartAction reviews deep reports and opted-in simple reports", () => {
  assert.equal(
    getResearchStartAction({ ...settings, report_type: "deep" }),
    "review_outline",
  );
  assert.equal(getResearchStartAction(settings), "start_directly");
  assert.equal(
    getResearchStartAction({
      ...settings,
      confirm_outline_before_research: true,
    }),
    "review_outline",
  );
  assert.equal(
    getResearchStartAction({ ...settings, report_type: "detailed_report" }),
    "start_directly",
  );
});

test("prepareResearchStart does not request an outline for a simple report", async () => {
  let requestCount = 0;
  const result = await prepareResearchStart({
    task: "研究主题",
    settings,
    requestOutline: async () => {
      requestCount += 1;
      return { sections: outline, model_profile: "simple" };
    },
  });

  assert.deepEqual(result, { action: "start_directly" });
  assert.equal(requestCount, 0);
});

test("prepareResearchStart requests a simple outline when the preference is enabled", async () => {
  let capturedRequest: unknown;
  const result = await prepareResearchStart({
    task: "研究主题",
    settings: {
      ...settings,
      confirm_outline_before_research: true,
    },
    requestOutline: async (request) => {
      capturedRequest = request;
      return { sections: outline, model_profile: "simple" };
    },
  });

  assert.deepEqual(capturedRequest, {
    task: "研究主题",
    language: "Chinese (Simplified)",
    report_type: "research_report",
    model_profile: "simple",
  });
  assert.deepEqual(result, { action: "review_outline", sections: outline });
});

test("prepareResearchStart requests an outline before deep research", async () => {
  let capturedRequest: unknown;
  const result = await prepareResearchStart({
    task: "研究主题",
    settings: { ...settings, report_type: "deep" },
    requestOutline: async (request) => {
      capturedRequest = request;
      return { sections: outline, model_profile: "deep" };
    },
  });

  assert.deepEqual(capturedRequest, {
    task: "研究主题",
    language: "Chinese (Simplified)",
    report_type: "deep",
    model_profile: "deep",
  });
  assert.deepEqual(result, { action: "review_outline", sections: outline });
});

test("buildResearchStartPayload includes a confirmed outline for opted-in simple research", () => {
  const payload = buildResearchStartPayload({
    task: "研究主题",
    settings: {
      ...settings,
      confirm_outline_before_research: true,
    },
    queryDomains: [],
    execution: { outline, model_profile: "simple" },
  });

  assert.equal(payload.model_profile, "simple");
  assert.deepEqual(payload.outline, outline);
});

test("buildResearchStartPayload leaves simple requests unchanged", () => {
  const payload = buildResearchStartPayload({
    task: "研究主题",
    settings,
    queryDomains: ["example.com"],
  });

  assert.equal(payload.task, "研究主题");
  assert.equal(payload.report_type, "research_report");
  assert.deepEqual(payload.query_domains, ["example.com"]);
  assert.ok(!("outline" in payload));
  assert.ok(!("model_profile" in payload));
});

test("buildResearchStartPayload includes a confirmed outline for deep research", () => {
  const payload = buildResearchStartPayload({
    task: "研究主题",
    settings: { ...settings, report_type: "deep" },
    queryDomains: [],
    execution: { outline, model_profile: "deep" },
  });

  assert.equal(payload.model_profile, "deep");
  assert.deepEqual(payload.outline, outline);
});

test("buildResearchStartMessage serializes the confirmed outline for WebSocket", () => {
  const message = buildResearchStartMessage({
    task: "研究主题",
    settings: { ...settings, report_type: "deep" },
    queryDomains: [],
    execution: { outline, model_profile: "deep" },
  });

  assert.match(message, /^start /);
  const payload = JSON.parse(message.slice(6));
  assert.equal(payload.model_profile, "deep");
  assert.deepEqual(payload.outline, outline);
});

test("buildResearchStartPayload rejects deep execution without an outline", () => {
  assert.throws(
    () =>
      buildResearchStartPayload({
        task: "研究主题",
        settings: { ...settings, report_type: "deep" },
        queryDomains: [],
        execution: { model_profile: "deep" },
      }),
    /confirmed outline/i,
  );
});

test("buildResearchStartPayload rejects an outline with the wrong model profile", () => {
  assert.throws(
    () =>
      buildResearchStartPayload({
        task: "研究主题",
        settings: {
          ...settings,
          confirm_outline_before_research: true,
        },
        queryDomains: [],
        execution: { outline, model_profile: "deep" },
      }),
    /model profile/i,
  );
});

test("buildResearchStartPayload rejects opted-in simple execution without an outline", () => {
  assert.throws(
    () =>
      buildResearchStartPayload({
        task: "研究主题",
        settings: {
          ...settings,
          confirm_outline_before_research: true,
        },
        queryDomains: [],
      }),
    /confirmed outline/i,
  );
});
