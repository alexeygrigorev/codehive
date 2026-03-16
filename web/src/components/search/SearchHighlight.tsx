interface SearchHighlightProps {
  text: string;
  query: string;
}

export default function SearchHighlight({
  text,
  query,
}: SearchHighlightProps) {
  if (!query.trim()) {
    return <>{text}</>;
  }

  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escaped})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? <mark key={i}>{part}</mark> : part,
      )}
    </>
  );
}
