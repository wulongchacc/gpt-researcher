import type {
  ChatBoxSettings,
  OutlineRequest,
  OutlineResponse,
  OutlineSection,
  ResearchExecutionOptions,
} from "../types/data";

export type ResearchStartAction = "start_directly" | "review_outline";

export interface ResearchStartPayload {
  task: string;
  report_type: string;
  report_source: string;
  tone: string;
  language: ChatBoxSettings["language"];
  query_domains: string[];
  mcp_enabled: boolean;
  mcp_strategy: string;
  mcp_configs: ChatBoxSettings["mcp_configs"];
  outline?: OutlineSection[];
  model_profile?: "deep";
}

interface BuildResearchStartPayloadOptions {
  task: string;
  settings: ChatBoxSettings;
  queryDomains: string[];
  execution?: ResearchExecutionOptions;
}

export const getResearchStartAction = (
  reportType: string,
): ResearchStartAction =>
  reportType === "deep" ? "review_outline" : "start_directly";

interface PrepareResearchStartOptions {
  task: string;
  settings: ChatBoxSettings;
  requestOutline: (request: OutlineRequest) => Promise<OutlineResponse>;
}

export type PreparedResearchStart =
  | { action: "start_directly" }
  | { action: "review_outline"; sections: OutlineSection[] };

export const prepareResearchStart = async ({
  task,
  settings,
  requestOutline,
}: PrepareResearchStartOptions): Promise<PreparedResearchStart> => {
  const action = getResearchStartAction(settings.report_type);
  if (action === "start_directly") return { action };

  const response = await requestOutline({
    task,
    language: settings.language,
  });
  return { action, sections: response.sections };
};

export const buildResearchStartPayload = ({
  task,
  settings,
  queryDomains,
  execution,
}: BuildResearchStartPayloadOptions): ResearchStartPayload => {
  if (
    settings.report_type === "deep" &&
    (!execution?.outline || execution.outline.length === 0)
  ) {
    throw new Error("Deep research requires a confirmed outline");
  }

  const payload: ResearchStartPayload = {
    task,
    report_type: settings.report_type,
    report_source: settings.report_source,
    tone: settings.tone,
    language: settings.language,
    query_domains: queryDomains,
    mcp_enabled: settings.mcp_enabled || false,
    mcp_strategy: settings.mcp_strategy || "fast",
    mcp_configs: settings.mcp_configs || [],
  };

  if (settings.report_type === "deep" && execution?.outline) {
    payload.outline = execution.outline;
    payload.model_profile = "deep";
  }

  return payload;
};

export const buildResearchStartMessage = (
  options: BuildResearchStartPayloadOptions,
): string => `start ${JSON.stringify(buildResearchStartPayload(options))}`;
