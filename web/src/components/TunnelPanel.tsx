import { useEffect, useState } from "react";
import {
  fetchTunnels,
  createTunnel,
  closeTunnel,
} from "@/api/tunnels";
import type { TunnelRead } from "@/api/tunnels";

export default function TunnelPanel() {
  const [tunnels, setTunnels] = useState<TunnelRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [targetId, setTargetId] = useState("");
  const [remotePort, setRemotePort] = useState("");
  const [localPort, setLocalPort] = useState("");
  const [label, setLabel] = useState("");

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchTunnels();
      setTunnels(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch tunnels",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function initialLoad() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchTunnels();
        if (!cancelled) {
          setTunnels(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to fetch tunnels",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    initialLoad();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate() {
    if (!targetId || !remotePort || !localPort) return;
    try {
      setError(null);
      await createTunnel({
        target_id: targetId,
        remote_port: Number(remotePort),
        local_port: Number(localPort),
        label: label || undefined,
      });
      setTargetId("");
      setRemotePort("");
      setLocalPort("");
      setLabel("");
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create tunnel",
      );
    }
  }

  async function handleClose(tunnelId: string) {
    try {
      setError(null);
      await closeTunnel(tunnelId);
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to close tunnel",
      );
    }
  }

  function statusColor(status: string): string {
    switch (status) {
      case "active":
        return "text-green-600";
      case "disconnected":
        return "text-yellow-600";
      case "closed":
        return "text-gray-400";
      default:
        return "text-gray-500";
    }
  }

  if (loading) {
    return <p className="text-gray-500">Loading tunnels...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <input
          type="text"
          placeholder="Target ID"
          aria-label="Target ID"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          className="rounded border px-2 py-1 text-sm"
        />
        <input
          type="number"
          placeholder="Remote Port"
          aria-label="Remote Port"
          value={remotePort}
          onChange={(e) => setRemotePort(e.target.value)}
          className="rounded border px-2 py-1 text-sm"
        />
        <input
          type="number"
          placeholder="Local Port"
          aria-label="Local Port"
          value={localPort}
          onChange={(e) => setLocalPort(e.target.value)}
          className="rounded border px-2 py-1 text-sm"
        />
        <input
          type="text"
          placeholder="Label"
          aria-label="Label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="rounded border px-2 py-1 text-sm"
        />
        <button
          type="button"
          onClick={handleCreate}
          className="rounded bg-blue-500 px-3 py-1 text-sm text-white hover:bg-blue-600"
        >
          Create Tunnel
        </button>
      </div>

      {tunnels.length === 0 ? (
        <p className="text-gray-500">No active tunnels</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-gray-500">
              <th className="py-1">Label</th>
              <th className="py-1">Target</th>
              <th className="py-1">Remote Port</th>
              <th className="py-1">Local Port</th>
              <th className="py-1">Status</th>
              <th className="py-1">Preview</th>
              <th className="py-1">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tunnels.map((t) => (
              <tr key={t.id} className="border-b">
                <td className="py-1">{t.label || t.id}</td>
                <td className="py-1 font-mono text-xs">{t.target_id}</td>
                <td className="py-1">{t.remote_port}</td>
                <td className="py-1">{t.local_port}</td>
                <td className={`py-1 font-medium ${statusColor(t.status)}`}>
                  {t.status}
                </td>
                <td className="py-1">
                  <a
                    href={`http://localhost:${t.local_port}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    Open
                  </a>
                </td>
                <td className="py-1">
                  <button
                    type="button"
                    onClick={() => handleClose(t.id)}
                    className="rounded bg-red-500 px-2 py-0.5 text-xs text-white hover:bg-red-600"
                  >
                    Close
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
