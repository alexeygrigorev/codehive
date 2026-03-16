import { apiClient } from "./client";

export async function downloadTranscript(
  sessionId: string,
  format: "json" | "markdown",
  sessionName?: string,
): Promise<void> {
  const response = await apiClient.get(
    `/api/sessions/${sessionId}/transcript?format=${format}`,
  );

  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }

  if (format === "markdown") {
    const text = await response.text();
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `session-${sessionName ?? sessionId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } else {
    const data = await response.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `session-${sessionName ?? sessionId}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}
