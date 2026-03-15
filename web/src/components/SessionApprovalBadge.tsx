import { useNotifications } from "@/hooks/useNotifications";
import ApprovalBadge from "./ApprovalBadge";

export default function SessionApprovalBadge() {
  const { pendingApprovals } = useNotifications();
  return <ApprovalBadge count={pendingApprovals} />;
}
