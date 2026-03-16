import React, { useCallback, useEffect, useState } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type {
  RootTabParamList,
  DashboardStackParamList,
  SessionsStackParamList,
} from "./types";

import DashboardScreen from "../screens/DashboardScreen";
import ProjectSessionsScreen from "../screens/ProjectSessionsScreen";
import SessionsScreen from "../screens/SessionsScreen";
import SessionDetailScreen from "../screens/SessionDetailScreen";
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
        name="ProjectSessions"
        component={ProjectSessionsScreen}
        options={{ title: "Sessions" }}
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
