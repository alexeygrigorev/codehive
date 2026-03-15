export interface ApprovalBadgeProps {
  count: number;
}

export default function ApprovalBadge({ count }: ApprovalBadgeProps) {
  if (count <= 0) {
    return null;
  }

  return (
    <span className="approval-badge inline-flex items-center justify-center rounded-full bg-red-600 text-white text-xs font-bold min-w-[1.25rem] h-5 px-1.5">
      {count}
    </span>
  );
}
