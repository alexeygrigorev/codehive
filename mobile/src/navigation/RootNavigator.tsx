import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { RootTabParamList, DashboardStackParamList } from "./types";

import DashboardScreen from "../screens/DashboardScreen";
import ProjectSessionsScreen from "../screens/ProjectSessionsScreen";
import SessionsScreen from "../screens/SessionsScreen";
import QuestionsScreen from "../screens/QuestionsScreen";
import SettingsScreen from "../screens/SettingsScreen";

const Tab = createBottomTabNavigator<RootTabParamList>();
const DashboardStack = createNativeStackNavigator<DashboardStackParamList>();

function DashboardStackNavigator() {
  return (
    <DashboardStack.Navigator>
      <DashboardStack.Screen
        name="DashboardHome"
        component={DashboardScreen}
        options={{ title: "Dashboard" }}
      />
      <DashboardStack.Screen
        name="ProjectSessions"
        component={ProjectSessionsScreen}
        options={{ title: "Sessions" }}
      />
    </DashboardStack.Navigator>
  );
}

export default function RootNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerShown: false }}>
        <Tab.Screen name="Dashboard" component={DashboardStackNavigator} />
        <Tab.Screen name="Sessions" component={SessionsScreen} />
        <Tab.Screen name="Questions" component={QuestionsScreen} />
        <Tab.Screen name="Settings" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
