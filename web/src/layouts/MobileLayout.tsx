import { Outlet } from "react-router-dom";
import MobileNav from "@/components/mobile/MobileNav";

export default function MobileLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-gray-50 dark:bg-gray-900">
      <main className="flex-1 p-4 pb-20">
        <Outlet />
      </main>
      <MobileNav />
    </div>
  );
}
