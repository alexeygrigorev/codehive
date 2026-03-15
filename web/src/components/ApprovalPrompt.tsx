export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface ApprovalPromptProps {
  actionId: string;
  description: string;
  status?: ApprovalStatus;
  loading?: boolean;
  onApprove: (actionId: string) => void;
  onReject: (actionId: string) => void;
}

export default function ApprovalPrompt({
  actionId,
  description,
  status = "pending",
  loading = false,
  onApprove,
  onReject,
}: ApprovalPromptProps) {
  const isPending = status === "pending";

  return (
    <div className="approval-prompt rounded-lg border border-amber-200 bg-amber-50 p-3 my-2">
      <p className="text-sm font-medium text-amber-900 mb-2">
        Approval Required
      </p>
      <p className="approval-description text-sm text-amber-800 mb-3">
        {description}
      </p>
      {isPending ? (
        <div className="flex gap-2">
          <button
            type="button"
            className="approve-button rounded px-3 py-1 text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading}
            onClick={() => onApprove(actionId)}
          >
            Approve
          </button>
          <button
            type="button"
            className="reject-button rounded px-3 py-1 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading}
            onClick={() => onReject(actionId)}
          >
            Reject
          </button>
        </div>
      ) : (
        <p
          className={`approval-resolved text-sm font-medium ${status === "approved" ? "text-green-700" : "text-red-700"}`}
        >
          {status === "approved" ? "Approved" : "Rejected"}
        </p>
      )}
    </div>
  );
}
