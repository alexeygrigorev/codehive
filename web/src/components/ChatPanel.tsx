import { useEffect, useRef, useCallback, useMemo, useState } from "react";
import { useSessionEvents } from "@/hooks/useSessionEvents";
import { normalizeEvent } from "@/api/websocket";
import type { SessionEvent } from "@/api/websocket";
import { useWebSocket } from "@/context/WebSocketContext";
import { approveAction, rejectAction } from "@/api/approvals";
import MessageBubble from "./MessageBubble";
import ToolCallResult from "./ToolCallResult";
import SubAgentEventCard from "./SubAgentEventCard";
import ApprovalPrompt from "./ApprovalPrompt";
import type { ApprovalStatus } from "./ApprovalPrompt";
import ThinkingIndicator from "./ThinkingIndicator";
import ChatInput from "./ChatInput";
import ExportButton from "./ExportButton";
import { sendMessage } from "@/api/messages";

interface ChatItem {
  id: string;
  kind: "message" | "tool_call" | "approval" | "subagent_event";
  event: SessionEvent;
  finishEvent?: SessionEvent;
}

export interface ChatPanelProps {
  sessionId: string;
  sessionName?: string;
  onFirstMessage?: (content: string) => void;
}

const CHAT_EVENT_TYPES = [
  "message.created",
  "message.delta",
  "tool.call.started",
  "tool.call.finished",
  "approval.required",
  "context.compacted",
  "subagent.spawned",
  "subagent.report",
  "error",
];

export default function ChatPanel({ sessionId, sessionName, onFirstMessage }: ChatPanelProps) {
  const events = useSessionEvents(CHAT_EVENT_TYPES);
  const { injectEvents } = useWebSocket();
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);
  const firstMessageSentRef = useRef(false);
  const [sending, setSending] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [approvalStates, setApprovalStates] = useState<
    Record<string, { status: ApprovalStatus; loading: boolean }>
  >({});

  const chatItems = useMemo(() => {
    const items: ChatItem[] = [];
    const toolCallMap = new Map<string, ChatItem>();
    let streamingBuffer = "";
    let streamingId: string | null = null;

    for (const event of events) {
      if (event.type === "message.delta") {
        const content = event.data.content as string;
        if (content) {
          streamingBuffer += content;
          if (!streamingId) {
            streamingId = `streaming-${event.id}`;
          }
          // Update or create the streaming message item
          const existing = items.find((i) => i.id === streamingId);
          if (existing) {
            existing.event = {
              ...event,
              type: "message.created",
              data: { ...event.data, role: "assistant", content: streamingBuffer },
            };
          } else {
            items.push({
              id: streamingId,
              kind: "message",
              event: {
                ...event,
                type: "message.created",
                data: { ...event.data, role: "assistant", content: streamingBuffer },
              },
            });
          }
        }
      } else if (event.type === "message.created") {
        if (event.data.role === "assistant" && streamingId) {
          // Final message replaces the streaming buffer
          const existing = items.find((i) => i.id === streamingId);
          if (existing) {
            existing.event = event;
            existing.id = event.id;
          } else {
            items.push({ id: event.id, kind: "message", event });
          }
          streamingBuffer = "";
          streamingId = null;
        } else {
          items.push({ id: event.id, kind: "message", event });
        }
      } else if (event.type === "tool.call.started") {
        // Finalize any streaming before tool calls
        streamingBuffer = "";
        streamingId = null;
        const item: ChatItem = { id: event.id, kind: "tool_call", event };
        items.push(item);
        const callId = (event.data.call_id as string) ?? event.id;
        toolCallMap.set(callId, item);
      } else if (event.type === "tool.call.finished") {
        const callId = (event.data.call_id as string) ?? event.id;
        const existing = toolCallMap.get(callId);
        if (existing) {
          existing.finishEvent = event;
        } else {
          items.push({
            id: event.id,
            kind: "tool_call",
            event,
            finishEvent: event,
          });
        }
      } else if (event.type === "error") {
        items.push({
          id: event.id,
          kind: "message",
          event: {
            ...event,
            type: "message.created",
            data: {
              role: "error",
              content: (event.data.content as string) ?? "Unknown error",
            },
          },
        });
      } else if (event.type === "approval.required") {
        items.push({ id: event.id, kind: "approval", event });
      } else if (
        event.type === "subagent.spawned" ||
        event.type === "subagent.report"
      ) {
        items.push({ id: event.id, kind: "subagent_event", event });
      } else if (event.type === "context.compacted") {
        const mc = event.data.messages_compacted ?? 0;
        const mp = event.data.messages_preserved ?? 0;
        items.push({
          id: event.id,
          kind: "message",
          event: {
            ...event,
            type: "message.created",
            data: {
              role: "system",
              content: `Context compacted: ${mc} messages summarized, ${mp} preserved`,
            },
          },
        });
      }
    }

    return items;
  }, [events]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    autoScrollRef.current = atBottom;
  }, []);

  // Detect if session already has user messages (e.g. re-entering existing session)
  useEffect(() => {
    const hasUserMessage = chatItems.some(
      (item) => item.kind === "message" && item.event.data.role === "user",
    );
    if (hasUserMessage) {
      firstMessageSentRef.current = true;
    }
  }, [chatItems]);

  useEffect(() => {
    if (autoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatItems, isThinking]);

  const handleSend = useCallback(
    async (content: string) => {
      setSending(true);
      setIsThinking(true);

      // Optimistic: inject user message immediately so it renders before SSE
      const optimisticId = `optimistic-${crypto.randomUUID()}`;
      const optimisticEvent: SessionEvent = {
        id: optimisticId,
        session_id: sessionId,
        type: "message.created",
        data: { role: "user", content },
        created_at: new Date().toISOString(),
      };
      injectEvents([optimisticEvent]);

      try {
        await sendMessage(sessionId, content, (rawEvent) => {
          const normalized = normalizeEvent(
            rawEvent as unknown as Record<string, unknown>,
          );
          // Skip the server's user message echo to avoid duplicates
          if (
            normalized.type === "message.created" &&
            normalized.data.role === "user"
          ) {
            return;
          }
          injectEvents([normalized]);
          // Stop thinking on first assistant content or error
          if (
            normalized.type === "message.delta" ||
            (normalized.type === "message.created" &&
              normalized.data.role === "assistant") ||
            normalized.type === "tool.call.started" ||
            normalized.type === "error"
          ) {
            setIsThinking(false);
          }
        });
        if (!firstMessageSentRef.current) {
          firstMessageSentRef.current = true;
          onFirstMessage?.(content);
        }
      } finally {
        setSending(false);
        setIsThinking(false);
      }
    },
    [sessionId, injectEvents, onFirstMessage],
  );

  const handleApprove = useCallback(
    async (actionId: string) => {
      setApprovalStates((prev) => ({
        ...prev,
        [actionId]: { status: "pending", loading: true },
      }));
      try {
        await approveAction(sessionId, actionId);
        setApprovalStates((prev) => ({
          ...prev,
          [actionId]: { status: "approved", loading: false },
        }));
      } catch {
        setApprovalStates((prev) => ({
          ...prev,
          [actionId]: { status: "pending", loading: false },
        }));
      }
    },
    [sessionId],
  );

  const handleReject = useCallback(
    async (actionId: string) => {
      setApprovalStates((prev) => ({
        ...prev,
        [actionId]: { status: "pending", loading: true },
      }));
      try {
        await rejectAction(sessionId, actionId);
        setApprovalStates((prev) => ({
          ...prev,
          [actionId]: { status: "rejected", loading: false },
        }));
      } catch {
        setApprovalStates((prev) => ({
          ...prev,
          [actionId]: { status: "pending", loading: false },
        }));
      }
    },
    [sessionId],
  );

  return (
    <div className="chat-panel flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Chat</span>
        <ExportButton sessionId={sessionId} sessionName={sessionName} />
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-3 p-4"
        onScroll={handleScroll}
      >
        {chatItems.length === 0 && (
          <p className="chat-empty text-center text-gray-400 dark:text-gray-500 mt-8">
            No messages yet. Start the conversation.
          </p>
        )}
        {chatItems.map((item) => {
          if (item.kind === "message") {
            return (
              <MessageBubble
                key={item.id}
                role={item.event.data.role as string}
                content={item.event.data.content as string}
              />
            );
          }
          if (item.kind === "subagent_event") {
            const d = item.event.data;
            return (
              <SubAgentEventCard
                key={item.id}
                eventType={
                  item.event.type as "subagent.spawned" | "subagent.report"
                }
                childName={d.child_name as string | undefined}
                childSessionId={d.child_session_id as string | undefined}
                engine={d.engine as string | undefined}
                mission={d.mission as string | undefined}
                status={d.status as string | undefined}
                summary={d.summary as string | undefined}
                filesChanged={d.files_changed as number | undefined}
              />
            );
          }
          if (item.kind === "approval") {
            const actionId = (item.event.data.action_id as string) ?? item.id;
            const description =
              (item.event.data.description as string) ??
              (item.event.data.tool_name as string) ??
              "Unknown action";
            const state = approvalStates[actionId];
            return (
              <ApprovalPrompt
                key={item.id}
                actionId={actionId}
                description={description}
                status={state?.status ?? "pending"}
                loading={state?.loading ?? false}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            );
          }
          const startData = item.event.data;
          const finishData = item.finishEvent?.data;
          return (
            <ToolCallResult
              key={item.id}
              toolName={(startData.tool_name as string) ?? "unknown"}
              input={startData.input as string | undefined}
              output={finishData?.output as string | undefined}
              isError={finishData?.is_error === true}
              finished={!!item.finishEvent}
            />
          );
        })}
        {isThinking && <ThinkingIndicator />}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
