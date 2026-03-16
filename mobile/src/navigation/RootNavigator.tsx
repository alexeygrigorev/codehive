import React from "react";
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
import SettingsScreen from "../screens/SettingsScreen";

const Tab = createBottomTabNavigator<RootTabParamList>();
const DashboardStackNav =
  createNativeStackNavigator<DashboardStackParamList>();
const SessionsStackNav =
  createNativeStackNavigator<SessionsStackParamList>();

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
  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerShown: false }}>
        <Tab.Screen name="Dashboard" component={DashboardStackNavigator} />
        <Tab.Screen name="Sessions" component={SessionsStackNavigator} />
        <Tab.Screen name="Questions" component={QuestionsScreen} />
        <Tab.Screen name="Settings" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
