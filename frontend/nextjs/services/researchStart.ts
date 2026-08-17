import type {
  ChatBoxSettings,
  ModelProfile,
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
  model_profile?: ModelProfile;
}

interface BuildResearchStartPayloadOptions {
  task: string;
  settings: ChatBoxSettings;
  queryDomains: string[];
  execution?: ResearchExecutionOptions;
}

const getModelProfile = (reportType: string): ModelProfile =>
  reportType === "deep" ? "deep" : "simple";

export const getResearchStartAction = (
  settingsOrReportType: ChatBoxSettings | string,
): ResearchStartAction => {
  if (typeof settingsOrReportType === "string") {
    return settingsOrReportType === "deep"
      ? "review_outline"
      : "start_directly";
  }

  return settingsOrReportType.report_type === "deep" ||
    (settingsOrReportType.report_type === "research_report" &&
      settingsOrReportType.confirm_outline_before_research)
    ? "review_outline"
    : "start_directly";
};

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
  const action = getResearchStartAction(settings);
  if (action === "start_directly") return { action };

  const modelProfile = getModelProfile(settings.report_type);

  const response = await requestOutline({
    task,
    language: settings.language,
    report_type: settings.report_type === "deep" ? "deep" : "research_report",
    model_profile: modelProfile,
  });
  return { action, sections: response.sections };
};

export const buildResearchStartPayload = ({
  task,
  settings,
  queryDomains,
  execution,
}: BuildResearchStartPayloadOptions): ResearchStartPayload => {
  const requiresOutline =
    settings.report_type === "deep" ||
    (settings.report_type === "research_report" &&
      settings.confirm_outline_before_research);

  if (
    requiresOutline &&
    (!execution?.outline || execution.outline.length === 0)
  ) {
    throw new Error("Research requires a confirmed outline");
  }

  if (execution?.outline) {
    const expectedProfile = getModelProfile(settings.report_type);
    if (execution.model_profile !== expectedProfile) {
      throw new Error(
        `Outline model profile must be ${expectedProfile} for ${settings.report_type}`,
      );
    }
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

  if (execution?.outline) {
    payload.outline = execution.outline;
    payload.model_profile = execution.model_profile;
  }

  return payload;
};

export const buildResearchStartMessage = (
  options: BuildResearchStartPayloadOptions,
): string => `start ${JSON.stringify(buildResearchStartPayload(options))}`;
