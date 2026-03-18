export interface MessageBubbleProps {
  role: string;
  content: string;
}

const roleStyles: Record<string, string> = {
  user: "ml-auto bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100",
  assistant:
    "mr-auto bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100",
  system:
    "mx-auto bg-yellow-50 text-yellow-800 text-center italic dark:bg-yellow-900 dark:text-yellow-200",
  tool: "mr-auto bg-gray-800 text-green-300 font-mono text-sm dark:bg-gray-950 dark:text-green-400",
};

export default function MessageBubble({ role, content }: MessageBubbleProps) {
  const style = roleStyles[role] ?? roleStyles.assistant;

  return (
    <div
      className={`message-bubble message-${role} max-w-[80%] rounded-lg px-4 py-2 ${style}`}
      data-role={role}
    >
      <p className="whitespace-pre-wrap">{content}</p>
    </div>
  );
}
