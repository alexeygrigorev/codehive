export interface PendingApproval {
  actionId: string;
  description: string;
}

export interface QuickActionsProps {
  pendingApprovals: PendingApproval[];
  onApprove: (actionId: string) => void;
  onReject: (actionId: string) => void;
  loading?: boolean;
}

export default function QuickActions({
  pendingApprovals,
  onApprove,
  onReject,
  loading = false,
}: QuickActionsProps) {
  if (pendingApprovals.length === 0) {
    return null;
  }

  const first = pendingApprovals[0];

  return (
    <div
      className="fixed bottom-16 left-4 right-4 z-40 rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/30 p-3 shadow-lg"
      data-testid="quick-actions"
    >
      <p className="text-sm text-amber-900 dark:text-amber-200 mb-2 truncate">
        {first.description}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className="flex-1 rounded bg-green-600 px-4 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          style={{ minHeight: "44px", minWidth: "44px" }}
          disabled={loading}
          onClick={() => onApprove(first.actionId)}
        >
          Approve
        </button>
        <button
          type="button"
          className="flex-1 rounded bg-red-600 px-4 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          style={{ minHeight: "44px", minWidth: "44px" }}
          disabled={loading}
          onClick={() => onReject(first.actionId)}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
