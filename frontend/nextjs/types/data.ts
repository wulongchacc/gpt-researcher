export interface BaseData {
  type: string;
}

export interface BasicData extends BaseData {
  type: 'basic';
  content: string;
}

export interface LanggraphButtonData extends BaseData {
  type: 'langgraphButton';
  link: string;
}

export interface DifferencesData extends BaseData {
  type: 'differences';
  content: string;
  output: string;
}

export interface QuestionData extends BaseData {
  type: 'question';
  content: string;
}

export interface ChatData extends BaseData {
  type: 'chat';
  content: string;
  metadata?: any; // For storing search results and other contextual information
}

export type Data = BasicData | LanggraphButtonData | DifferencesData | QuestionData | ChatData;

export interface MCPConfig {
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
}

export type ReportLanguage = "Chinese (Simplified)" | "English";
export type ModelProfile = "simple" | "deep";

export interface OutlineSection {
  id: string;
  title: string;
  description: string;
}

export interface OutlineRequest {
  task: string;
  language: ReportLanguage;
  report_type: "research_report" | "deep";
  model_profile: ModelProfile;
}

export interface OutlineResponse {
  sections: OutlineSection[];
  model_profile: ModelProfile;
}

export interface ResearchExecutionOptions {
  outline?: OutlineSection[];
  model_profile?: ModelProfile;
}

export interface ChatBoxSettings {
  report_type: string;
  report_source: string;
  tone: string;
  domains: string[];
  defaultReportType: string;
  layoutType: string;
  mcp_enabled: boolean;
  mcp_configs: MCPConfig[];
  mcp_strategy?: string;
  language: ReportLanguage;
  confirm_outline_before_research?: boolean;
}

export interface Domain {
  value: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: number;
  metadata?: any; // For storing search results and other contextual information
}

export interface ResearchHistoryItem {
  id: string;
  question: string;
  answer: string;
  timestamp: number;
  orderedData: Data[];
  chatMessages?: ChatMessage[];
}
