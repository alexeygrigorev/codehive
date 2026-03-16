import React, { useCallback, useEffect, useState } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type {
  RootTabParamList,
  DashboardStackParamList,
  SessionsStackParamList,
  SearchStackParamList,
} from "./types";

import DashboardScreen from "../screens/DashboardScreen";
import NewProjectScreen from "../screens/NewProjectScreen";
import FlowChatScreen from "../screens/FlowChatScreen";
import BriefReviewScreen from "../screens/BriefReviewScreen";
import ProjectSessionsScreen from "../screens/ProjectSessionsScreen";
import ProjectIssuesScreen from "../screens/ProjectIssuesScreen";
import SessionsScreen from "../screens/SessionsScreen";
import SessionDetailScreen from "../screens/SessionDetailScreen";
import SearchScreen from "../screens/SearchScreen";
import QuestionsScreen from "../screens/QuestionsScreen";
import ApprovalsScreen from "../screens/ApprovalsScreen";
import SettingsScreen from "../screens/SettingsScreen";
import { listQuestions } from "../api/questions";
import { listPendingApprovals } from "../api/approvals";

const Tab = createBottomTabNavigator<RootTabParamList>();
const DashboardStackNav =
  createNativeStackNavigator<DashboardStackParamList>();
const SessionsStackNav =
  createNativeStackNavigator<SessionsStackParamList>();
const SearchStackNav =
  createNativeStackNavigator<SearchStackParamList>();

const BADGE_POLL_INTERVAL = 30000;

function DashboardStackNavigator() {
  return (
    <DashboardStackNav.Navigator>
      <DashboardStackNav.Screen
        name="DashboardHome"
        component={DashboardScreen}
        options={{ title: "Dashboard" }}
      />
      <DashboardStackNav.Screen
        name="NewProject"
        component={NewProjectScreen}
        options={{ title: "New Project" }}
      />
      <DashboardStackNav.Screen
        name="FlowChat"
        component={FlowChatScreen}
        options={{ title: "Project Setup" }}
      />
      <DashboardStackNav.Screen
        name="BriefReview"
        component={BriefReviewScreen}
        options={{ title: "Review Brief" }}
      />
      <DashboardStackNav.Screen
        name="ProjectSessions"
        component={ProjectSessionsScreen}
        options={{ title: "Sessions" }}
      />
      <DashboardStackNav.Screen
        name="ProjectIssues"
        component={ProjectIssuesScreen}
        options={{ title: "Issues" }}
      />
      <DashboardStackNav.Screen
        name="SessionDetail"
        component={SessionDetailScreen}
        options={{ headerShown: false }}
      />
    </DashboardStackNav.Navigator>
  );
}

function SessionsStackNavigator() {
  return (
    <SessionsStackNav.Navigator>
      <SessionsStackNav.Screen
        name="SessionsList"
        component={SessionsScreen}
        options={{ title: "Sessions" }}
      />
      <SessionsStackNav.Screen
        name="SessionDetail"
        component={SessionDetailScreen}
        options={{ headerShown: false }}
      />
    </SessionsStackNav.Navigator>
  );
}

function SearchStackNavigator() {
  return (
    <SearchStackNav.Navigator>
      <SearchStackNav.Screen
        name="SearchHome"
        component={SearchScreen}
        options={{ title: "Search" }}
      />
      <SearchStackNav.Screen
        name="SessionDetail"
        component={SessionDetailScreen}
        options={{ headerShown: false }}
      />
      <SearchStackNav.Screen
        name="ProjectIssues"
        component={ProjectIssuesScreen}
        options={{ title: "Issues" }}
      />
    </SearchStackNav.Navigator>
  );
}

export default function RootNavigator() {
  const [questionsBadge, setQuestionsBadge] = useState<number | undefined>(
    undefined,
  );
  const [approvalsBadge, setApprovalsBadge] = useState<number | undefined>(
    undefined,
  );

  const fetchBadgeCounts = useCallback(async () => {
    try {
      const questions = await listQuestions();
      const unanswered = questions.filter(
        (q: { answered: boolean }) => !q.answered,
      );
      setQuestionsBadge(unanswered.length > 0 ? unanswered.length : undefined);
    } catch {
      // silently handle
    }
    try {
      const approvals = await listPendingApprovals();
      setApprovalsBadge(
        approvals.length > 0 ? approvals.length : undefined,
      );
    } catch {
      // silently handle
    }
  }, []);

  useEffect(() => {
    fetchBadgeCounts();
    const interval = setInterval(fetchBadgeCounts, BADGE_POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchBadgeCounts]);

  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerShown: false }}>
        <Tab.Screen name="Dashboard" component={DashboardStackNavigator} />
        <Tab.Screen name="Sessions" component={SessionsStackNavigator} />
        <Tab.Screen name="Search" component={SearchStackNavigator} />
        <Tab.Screen
          name="Questions"
          component={QuestionsScreen}
          options={{ tabBarBadge: questionsBadge }}
        />
        <Tab.Screen
          name="Approvals"
          component={ApprovalsScreen}
          options={{ tabBarBadge: approvalsBadge }}
        />
        <Tab.Screen name="Settings" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
