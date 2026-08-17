import assert from "node:assert/strict";
import test from "node:test";

import {
  OutlineApiError,
  requestOutline,
} from "../services/outlineApi.ts";

const validDeepResponse = {
  sections: [
    { id: "section-1", title: "行业背景", description: "说明研究背景" },
    { id: "section-2", title: "市场现状", description: "分析当前市场" },
    { id: "section-3", title: "未来趋势", description: "总结未来趋势" },
  ],
  model_profile: "deep",
};

test("requestOutline posts the task and language to the outline endpoint", async () => {
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;
  const fetchImpl: typeof fetch = async (input, init) => {
    capturedUrl = String(input);
    capturedInit = init;
    return Response.json(validDeepResponse);
  };

  const result = await requestOutline(
    {
      task: "研究中国新能源汽车市场",
      language: "Chinese (Simplified)",
      report_type: "deep",
      model_profile: "deep",
    },
    { baseUrl: "http://localhost:8000/", fetchImpl },
  );

  assert.equal(capturedUrl, "http://localhost:8000/api/outline");
  assert.equal(capturedInit?.method, "POST");
  assert.deepEqual(capturedInit?.headers, { "Content-Type": "application/json" });
  assert.deepEqual(JSON.parse(String(capturedInit?.body)), {
    task: "研究中国新能源汽车市场",
    language: "Chinese (Simplified)",
    report_type: "deep",
    model_profile: "deep",
  });
  assert.deepEqual(result, validDeepResponse);
});

test("requestOutline accepts a matching simple response profile", async () => {
  let capturedBody: unknown;
  const fetchImpl: typeof fetch = async (_input, init) => {
    capturedBody = JSON.parse(String(init?.body));
    return Response.json({
      ...validDeepResponse,
      model_profile: "simple",
    });
  };

  const result = await requestOutline(
    {
      task: "研究中国新能源汽车市场",
      language: "Chinese (Simplified)",
      report_type: "research_report",
      model_profile: "simple",
    },
    { baseUrl: "http://localhost:8000/", fetchImpl },
  );

  assert.deepEqual(capturedBody, {
    task: "研究中国新能源汽车市场",
    language: "Chinese (Simplified)",
    report_type: "research_report",
    model_profile: "simple",
  });
  assert.equal(result.model_profile, "simple");
});

test("requestOutline rejects a response with a mismatched model profile", async () => {
  const fetchImpl: typeof fetch = async () =>
    Response.json(validDeepResponse);

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "research_report",
        model_profile: "simple",
      },
      { baseUrl: "http://localhost:8000", fetchImpl },
    ),
    (error: unknown) => {
      assert.ok(error instanceof OutlineApiError);
      assert.equal(error.code, "invalid_response");
      return true;
    },
  );
});

test("requestOutline exposes the backend error detail", async () => {
  const fetchImpl: typeof fetch = async () =>
    Response.json(
      { detail: "Unable to generate a valid research outline" },
      { status: 502 },
    );

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "deep",
        model_profile: "deep",
      },
      { baseUrl: "http://localhost:8000", fetchImpl },
    ),
    (error: unknown) => {
      assert.ok(error instanceof OutlineApiError);
      assert.equal(error.code, "server_error");
      assert.equal(error.status, 502);
      assert.match(error.message, /Unable to generate/);
      return true;
    },
  );
});

test("requestOutline rejects malformed successful responses", async () => {
  const fetchImpl: typeof fetch = async () =>
    Response.json({ sections: [{ id: "section-1", title: "" }] });

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "deep",
        model_profile: "deep",
      },
      { baseUrl: "http://localhost:8000", fetchImpl },
    ),
    (error: unknown) => {
      assert.ok(error instanceof OutlineApiError);
      assert.equal(error.code, "invalid_response");
      return true;
    },
  );
});

test("requestOutline classifies a non-JSON success response as invalid", async () => {
  const fetchImpl: typeof fetch = async () =>
    new Response("not json", {
      status: 200,
      headers: { "Content-Type": "text/plain" },
    });

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "deep",
        model_profile: "deep",
      },
      { baseUrl: "http://localhost:8000", fetchImpl },
    ),
    (error: unknown) => {
      assert.ok(error instanceof OutlineApiError);
      assert.equal(error.code, "invalid_response");
      return true;
    },
  );
});

test("requestOutline aborts a request after the configured timeout", async () => {
  const fetchImpl: typeof fetch = (_input, init) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        reject(new DOMException("Aborted", "AbortError"));
      });
    });

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "deep",
        model_profile: "deep",
      },
      { baseUrl: "http://localhost:8000", fetchImpl, timeoutMs: 5 },
    ),
    (error: unknown) => {
      assert.ok(error instanceof OutlineApiError);
      assert.equal(error.code, "timeout");
      return true;
    },
  );
});

test("requestOutline stops when the caller cancels the request", async () => {
  const controller = new AbortController();
  const fetchImpl: typeof fetch = (_input, init) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        reject(new DOMException("Aborted", "AbortError"));
      });
    });

  const request = requestOutline(
    {
      task: "研究主题",
      language: "Chinese (Simplified)",
      report_type: "deep",
      model_profile: "deep",
    },
    {
      baseUrl: "http://localhost:8000",
      fetchImpl,
      timeoutMs: 1_000,
      signal: controller.signal,
    },
  );
  controller.abort();

  await assert.rejects(request, (error: unknown) => {
    assert.ok(error instanceof OutlineApiError);
    assert.equal(error.code, "cancelled");
    return true;
  });
});

test("requestOutline reports cancellation when the caller signal is already cancelled", async () => {
  const controller = new AbortController();
  controller.abort();
  let fetchCount = 0;
  const fetchImpl: typeof fetch = async () => {
    fetchCount += 1;
    throw new DOMException("Aborted", "AbortError");
  };

  await assert.rejects(
    requestOutline(
      {
        task: "研究主题",
        language: "Chinese (Simplified)",
        report_type: "deep",
        model_profile: "deep",
      },
      {
        baseUrl: "http://localhost:8000",
        fetchImpl,
        signal: controller.signal,
      },
    ),
    (error: unknown) => {
      assert.ok(error instanceof OutlineApiError);
      assert.equal(error.code, "cancelled");
      return true;
    },
  );
  assert.equal(fetchCount, 1);
});
