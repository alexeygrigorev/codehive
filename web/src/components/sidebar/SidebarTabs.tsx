import { useState } from "react";
import TodoPanel from "./TodoPanel";
import ChangedFilesPanel from "./ChangedFilesPanel";
import ActivityPanel from "./ActivityPanel";
import SubAgentPanel from "./SubAgentPanel";
import QuestionsPanel from "./QuestionsPanel";
import CheckpointPanel from "./CheckpointPanel";
import AgentCommPanel from "./AgentCommPanel";
import SessionHistorySearch from "@/components/SessionHistorySearch";

export type TabKey =
  | "todo"
  | "changed-files"
  | "activity"
  | "sub-agents"
  | "comms"
  | "questions"
  | "checkpoints"
  | "search";

interface TabDef {
  key: TabKey;
  label: string;
}

const TABS: TabDef[] = [
  { key: "todo", label: "ToDo" },
  { key: "changed-files", label: "Changed Files" },
  { key: "activity", label: "Activity" },
  { key: "sub-agents", label: "Sub-agents" },
  { key: "comms", label: "Comms" },
  { key: "questions", label: "Questions" },
  { key: "checkpoints", label: "Checkpoints" },
  { key: "search", label: "Search" },
];

interface SidebarTabsProps {
  sessionId: string;
  activeTab?: TabKey;
  onTabChange?: (tab: TabKey) => void;
}

export default function SidebarTabs({
  sessionId,
  activeTab: controlledTab,
  onTabChange,
}: SidebarTabsProps) {
  const [internalTab, setInternalTab] = useState<TabKey>("todo");
  const activeTab = controlledTab ?? internalTab;

  function handleTabClick(tab: TabKey) {
    setInternalTab(tab);
    onTabChange?.(tab);
  }

  return (
    <div className="flex h-full flex-col">
      <div
        className="flex border-b border-gray-200"
        role="tablist"
        aria-label="Sidebar tabs"
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`sidebar-tab px-3 py-2 text-sm font-medium ${
              activeTab === tab.key
                ? "sidebar-tab-active border-b-2 border-blue-500 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
            onClick={() => handleTabClick(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto p-3" role="tabpanel">
        {activeTab === "todo" && <TodoPanel sessionId={sessionId} />}
        {activeTab === "changed-files" && (
          <ChangedFilesPanel sessionId={sessionId} />
        )}
        {activeTab === "activity" && <ActivityPanel sessionId={sessionId} />}
        {activeTab === "sub-agents" && <SubAgentPanel sessionId={sessionId} />}
        {activeTab === "comms" && <AgentCommPanel sessionId={sessionId} />}
        {activeTab === "questions" && <QuestionsPanel sessionId={sessionId} />}
        {activeTab === "checkpoints" && (
          <CheckpointPanel sessionId={sessionId} />
        )}
        {activeTab === "search" && (
          <SessionHistorySearch sessionId={sessionId} />
        )}
      </div>
    </div>
  );
}
