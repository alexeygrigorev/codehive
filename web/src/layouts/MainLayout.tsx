import { NavLink, Outlet } from "react-router-dom";

export default function MainLayout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-64 bg-gray-900 text-white flex-shrink-0">
        <div className="p-4">
          <h2 className="text-lg font-semibold">Codehive</h2>
        </div>
        <nav className="mt-4">
          <ul className="space-y-1">
            <li>
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `block px-4 py-2 text-sm ${
                    isActive
                      ? "bg-gray-800 text-white"
                      : "text-gray-300 hover:bg-gray-800 hover:text-white"
                  }`
                }
              >
                Dashboard
              </NavLink>
            </li>
          </ul>
        </nav>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
