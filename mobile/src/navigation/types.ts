import type { NavigatorScreenParams } from "@react-navigation/native";

// Stack param lists for each tab
export type DashboardStackParamList = {
  DashboardHome: undefined;
  ProjectSessions: { projectId: string; projectName: string };
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

export type SettingsStackParamList = {
  SettingsHome: undefined;
};

// Root bottom tab param list
export type RootTabParamList = {
  Dashboard: NavigatorScreenParams<DashboardStackParamList>;
  Sessions: NavigatorScreenParams<SessionsStackParamList>;
  Questions: NavigatorScreenParams<QuestionsStackParamList>;
  Settings: NavigatorScreenParams<SettingsStackParamList>;
};
