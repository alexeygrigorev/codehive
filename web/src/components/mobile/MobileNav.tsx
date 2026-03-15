import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/sessions", label: "Sessions", end: false },
  { to: "/approvals", label: "Approvals", end: false },
  { to: "/questions", label: "Questions", end: false },
];

export default function MobileNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-gray-200 bg-white"
      data-testid="mobile-nav"
    >
      <ul className="flex">
        {tabs.map((tab) => (
          <li key={tab.to} className="flex-1">
            <NavLink
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `flex items-center justify-center text-sm font-medium ${
                  isActive
                    ? "text-blue-600 font-semibold"
                    : "text-gray-500 hover:text-gray-700"
                }`
              }
              style={{ minHeight: "48px" }}
            >
              {tab.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
