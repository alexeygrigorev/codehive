import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">404 - Page Not Found</h1>
      <p className="text-gray-600 mt-2">
        The page you are looking for does not exist.
      </p>
      <Link to="/" className="text-blue-600 hover:underline mt-4 inline-block">
        Go back to Dashboard
      </Link>
    </div>
  );
}
