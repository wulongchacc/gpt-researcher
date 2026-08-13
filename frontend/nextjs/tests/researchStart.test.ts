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
};

const outline: OutlineSection[] = [
  { id: "section-1", title: "行业背景", description: "研究背景" },
  { id: "section-2", title: "市场现状", description: "研究市场" },
  { id: "section-3", title: "未来趋势", description: "研究趋势" },
];

test("getResearchStartAction routes only deep reports through outline review", () => {
  assert.equal(getResearchStartAction("deep"), "review_outline");
  assert.equal(getResearchStartAction("research_report"), "start_directly");
  assert.equal(getResearchStartAction("detailed_report"), "start_directly");
  assert.equal(getResearchStartAction("multi_agents"), "start_directly");
});

test("prepareResearchStart does not request an outline for a simple report", async () => {
  let requestCount = 0;
  const result = await prepareResearchStart({
    task: "研究主题",
    settings,
    requestOutline: async () => {
      requestCount += 1;
      return { sections: outline, model_profile: "deep" };
    },
  });

  assert.deepEqual(result, { action: "start_directly" });
  assert.equal(requestCount, 0);
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
  });
  assert.deepEqual(result, { action: "review_outline", sections: outline });
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
