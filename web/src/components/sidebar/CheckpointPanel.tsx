import CheckpointList from "@/components/CheckpointList";

interface CheckpointPanelProps {
  sessionId: string;
}

export default function CheckpointPanel({ sessionId }: CheckpointPanelProps) {
  return <CheckpointList sessionId={sessionId} />;
}
