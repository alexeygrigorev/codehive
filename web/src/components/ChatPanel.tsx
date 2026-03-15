import { useEffect, useRef, useCallback, useMemo, useState } from "react";
import { useSessionEvents } from "@/hooks/useSessionEvents";
import type { SessionEvent } from "@/api/websocket";
import { approveAction, rejectAction } from "@/api/approvals";
import MessageBubble from "./MessageBubble";
import ToolCallResult from "./ToolCallResult";
import ApprovalPrompt from "./ApprovalPrompt";
import type { ApprovalStatus } from "./ApprovalPrompt";
import ChatInput from "./ChatInput";
import { sendMessage } from "@/api/messages";

interface ChatItem {
  id: string;
  kind: "message" | "tool_call" | "approval";
  event: SessionEvent;
  finishEvent?: SessionEvent;
}

export interface ChatPanelProps {
  sessionId: string;
}

const CHAT_EVENT_TYPES = [
  "message.created",
  "tool.call.started",
  "tool.call.finished",
  "approval.required",
];

export default function ChatPanel({ sessionId }: ChatPanelProps) {
  const events = useSessionEvents(CHAT_EVENT_TYPES);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);
  const [sending, setSending] = useState(false);
  const [approvalStates, setApprovalStates] = useState<
    Record<string, { status: ApprovalStatus; loading: boolean }>
  >({});

  const chatItems = useMemo(() => {
    const items: ChatItem[] = [];
    const toolCallMap = new Map<string, ChatItem>();

    for (const event of events) {
      if (event.type === "message.created") {
        items.push({ id: event.id, kind: "message", event });
      } else if (event.type === "tool.call.started") {
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
      } else if (event.type === "approval.required") {
        items.push({ id: event.id, kind: "approval", event });
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

  useEffect(() => {
    if (autoScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatItems]);

  const handleSend = useCallback(
    async (content: string) => {
      setSending(true);
      try {
        await sendMessage(sessionId, content);
      } finally {
        setSending(false);
      }
    },
    [sessionId],
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
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-3 p-4"
        onScroll={handleScroll}
      >
        {chatItems.length === 0 && (
          <p className="chat-empty text-center text-gray-400 mt-8">
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
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
