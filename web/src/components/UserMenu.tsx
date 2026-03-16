import { useState } from "react";
import { useAuth } from "@/context/AuthContext";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  if (!user) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800 hover:text-white"
        aria-label="User menu"
      >
        <span>{user.username}</span>
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-48 rounded bg-gray-800 py-1 shadow-lg">
          <div className="border-b border-gray-700 px-4 py-2 text-sm text-gray-300">
            {user.username}
          </div>
          <button
            onClick={() => {
              logout();
              setOpen(false);
            }}
            className="block w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 hover:text-white"
          >
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
