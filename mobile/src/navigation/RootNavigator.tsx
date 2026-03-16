import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import type { RootTabParamList } from "./types";

import DashboardScreen from "../screens/DashboardScreen";
import SessionsScreen from "../screens/SessionsScreen";
import QuestionsScreen from "../screens/QuestionsScreen";
import SettingsScreen from "../screens/SettingsScreen";

const Tab = createBottomTabNavigator<RootTabParamList>();

export default function RootNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerShown: true }}>
        <Tab.Screen name="Dashboard" component={DashboardScreen} />
        <Tab.Screen name="Sessions" component={SessionsScreen} />
        <Tab.Screen name="Questions" component={QuestionsScreen} />
        <Tab.Screen name="Settings" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
