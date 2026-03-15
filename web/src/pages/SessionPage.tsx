import { useParams } from "react-router-dom";

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <div>
      <h1 className="text-2xl font-bold">Session</h1>
      <p className="text-gray-600 mt-2">Session ID: {sessionId}</p>
    </div>
  );
}
