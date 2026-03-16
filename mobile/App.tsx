import { StatusBar } from "expo-status-bar";
import { EventProvider } from "./src/context/EventContext";
import RootNavigator from "./src/navigation/RootNavigator";

export default function App() {
  return (
    <EventProvider>
      <RootNavigator />
      <StatusBar style="auto" />
    </EventProvider>
  );
}
