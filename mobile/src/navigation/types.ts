import type { NavigatorScreenParams } from "@react-navigation/native";
import type { FlowQuestion, ProjectBrief } from "../api/projectFlow";

// Stack param lists for each tab
export type DashboardStackParamList = {
  DashboardHome: undefined;
  NewProject: undefined;
  FlowChat: { flowId: string; questions: FlowQuestion[] };
  BriefReview: { flowId: string; brief: ProjectBrief };
  ProjectSessions: { projectId: string; projectName: string };
  ProjectIssues: { projectId: string; projectName: string };
  SessionDetail: { sessionId: string };
};

export type SessionsStackParamList = {
  SessionsList: undefined;
  SessionDetail: { sessionId: string };
};

export type QuestionsStackParamList = {
  QuestionsList: undefined;
  QuestionDetail: { questionId: string };
};

export type ApprovalsStackParamList = {
  ApprovalsList: undefined;
};

export type SearchStackParamList = {
  SearchHome: undefined;
  SessionDetail: { sessionId: string };
  ProjectIssues: { projectId: string; projectName: string };
};

export type SettingsStackParamList = {
  SettingsHome: undefined;
};

// Root bottom tab param list
export type RootTabParamList = {
  Dashboard: NavigatorScreenParams<DashboardStackParamList>;
  Sessions: NavigatorScreenParams<SessionsStackParamList>;
  Search: NavigatorScreenParams<SearchStackParamList>;
  Questions: NavigatorScreenParams<QuestionsStackParamList>;
  Approvals: NavigatorScreenParams<ApprovalsStackParamList>;
  Settings: NavigatorScreenParams<SettingsStackParamList>;
};
