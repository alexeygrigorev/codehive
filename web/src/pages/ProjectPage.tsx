import { useParams } from "react-router-dom";

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();

  return (
    <div>
      <h1 className="text-2xl font-bold">Project</h1>
      <p className="text-gray-600 mt-2">Project ID: {projectId}</p>
    </div>
  );
}
