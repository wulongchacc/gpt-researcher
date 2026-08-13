import type {
  OutlineRequest,
  OutlineResponse,
  OutlineSection,
} from "../types/data";

export type OutlineApiErrorCode =
  | "invalid_request"
  | "server_error"
  | "invalid_response"
  | "timeout"
  | "cancelled"
  | "network_error";

export class OutlineApiError extends Error {
  readonly code: OutlineApiErrorCode;
  readonly status?: number;

  constructor(
    message: string,
    code: OutlineApiErrorCode,
    status?: number,
  ) {
    super(message);
    this.name = "OutlineApiError";
    this.code = code;
    this.status = status;
  }
}

interface RequestOutlineOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  signal?: AbortSignal;
}

const DEFAULT_TIMEOUT_MS = 30_000;

const isOutlineSection = (value: unknown): value is OutlineSection => {
  if (!value || typeof value !== "object") return false;

  const section = value as Record<string, unknown>;
  return (
    typeof section.id === "string" &&
    section.id.trim().length > 0 &&
    typeof section.title === "string" &&
    section.title.trim().length > 0 &&
    typeof section.description === "string"
  );
};

const parseOutlineResponse = (value: unknown): OutlineResponse => {
  if (!value || typeof value !== "object") {
    throw new OutlineApiError("提纲接口返回了无效数据", "invalid_response");
  }

  const response = value as Record<string, unknown>;
  if (
    response.model_profile !== "deep" ||
    !Array.isArray(response.sections) ||
    response.sections.length < 3 ||
    response.sections.length > 5 ||
    !response.sections.every(isOutlineSection)
  ) {
    throw new OutlineApiError("提纲接口返回了无效数据", "invalid_response");
  }

  return response as unknown as OutlineResponse;
};

const readErrorDetail = async (response: Response): Promise<string> => {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
  } catch {
    // Fall back to a status-based message when the body is not JSON.
  }

  return `生成提纲失败（HTTP ${response.status}）`;
};

export const requestOutline = async (
  request: OutlineRequest,
  options: RequestOutlineOptions,
): Promise<OutlineResponse> => {
  const task = request.task.trim();
  if (!task) {
    throw new OutlineApiError("研究主题不能为空", "invalid_request");
  }

  const baseUrl = options.baseUrl;
  if (!baseUrl) {
    throw new OutlineApiError("无法确定后端服务地址", "invalid_request");
  }

  const controller = new AbortController();
  const abortFromExternalSignal = () => controller.abort();
  if (options.signal?.aborted) {
    controller.abort();
  } else {
    options.signal?.addEventListener("abort", abortFromExternalSignal, {
      once: true,
    });
  }
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );

  try {
    const response = await (options.fetchImpl ?? fetch)(
      new URL("api/outline", `${baseUrl.replace(/\/$/, "")}/`).toString(),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...request, task }),
        signal: controller.signal,
      },
    );

    if (!response.ok) {
      throw new OutlineApiError(
        await readErrorDetail(response),
        "server_error",
        response.status,
      );
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new OutlineApiError("提纲接口返回了无效数据", "invalid_response");
    }

    return parseOutlineResponse(body);
  } catch (error) {
    if (error instanceof OutlineApiError) throw error;
    if (options.signal?.aborted) {
      throw new OutlineApiError("已取消生成提纲", "cancelled");
    }
    if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      throw new OutlineApiError("生成提纲超时，请重试", "timeout");
    }

    throw new OutlineApiError("无法连接提纲服务，请检查网络后重试", "network_error");
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortFromExternalSignal);
  }
};
