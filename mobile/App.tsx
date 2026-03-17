import { useEffect } from "react";
import { StatusBar } from "expo-status-bar";
import { EventProvider } from "./src/context/EventContext";
import RootNavigator from "./src/navigation/RootNavigator";
import { checkAuthConfig } from "./src/api/client";

export default function App() {
  useEffect(() => {
    // Fetch auth config on startup so the API client knows whether to
    // attach Authorization headers.
    checkAuthConfig();
  }, []);

  return (
    <EventProvider>
      <RootNavigator />
      <StatusBar style="auto" />
    </EventProvider>
  );
}
