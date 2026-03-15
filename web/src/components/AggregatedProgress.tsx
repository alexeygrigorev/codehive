interface AggregatedProgressProps {
  total: number;
  completed: number;
}

export default function AggregatedProgress({
  total,
  completed,
}: AggregatedProgressProps) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="mb-3">
      <p className="mb-1 text-sm font-medium text-gray-700">
        {completed}/{total} completed
      </p>
      <div className="h-2 w-full rounded-full bg-gray-200">
        <div
          className="progress-bar h-2 rounded-full bg-blue-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
