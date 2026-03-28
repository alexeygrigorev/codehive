import { useEffect, useRef, useState } from "react";
import type { ModelInfo } from "@/api/providers";

interface Props {
  models: ModelInfo[];
  value: string;
  onChange: (value: string) => void;
}

export default function ModelCombobox({ models, value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Filter models by typed value (show all if value matches a known model id)
  const isExactMatch = models.some((m) => m.id === value);
  const filtered = isExactMatch
    ? models
    : models.filter(
        (m) =>
          m.id.toLowerCase().includes(value.toLowerCase()) ||
          m.name.toLowerCase().includes(value.toLowerCase()),
      );

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHighlightIndex((prev) =>
        prev < filtered.length - 1 ? prev + 1 : 0,
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      setHighlightIndex((prev) =>
        prev > 0 ? prev - 1 : filtered.length - 1,
      );
    } else if (e.key === "Enter" && open && highlightIndex >= 0) {
      e.preventDefault();
      const selected = filtered[highlightIndex];
      if (selected) {
        onChange(selected.id);
        setOpen(false);
        setHighlightIndex(-1);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setHighlightIndex(-1);
    }
  }

  function handleSelect(model: ModelInfo) {
    onChange(model.id);
    setOpen(false);
    setHighlightIndex(-1);
  }

  return (
    <div ref={wrapperRef} className="relative" data-testid="model-combobox">
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setHighlightIndex(-1);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm dark:bg-gray-700 dark:text-gray-100"
        data-testid="model-input"
        role="combobox"
        aria-expanded={open}
        aria-controls="model-listbox"
        aria-autocomplete="list"
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <ul
          id="model-listbox"
          ref={listboxRef}
          role="listbox"
          data-testid="model-listbox"
          className="absolute z-50 mt-1 w-full max-h-60 overflow-auto rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-lg"
        >
          {filtered.map((m, i) => (
            <li
              key={m.id}
              role="option"
              aria-selected={highlightIndex === i}
              className={`px-3 py-2 text-sm cursor-pointer ${
                highlightIndex === i
                  ? "bg-blue-100 dark:bg-blue-900"
                  : "hover:bg-gray-100 dark:hover:bg-gray-700"
              } dark:text-gray-100`}
              onMouseDown={(e) => {
                e.preventDefault();
                handleSelect(m);
              }}
              onMouseEnter={() => setHighlightIndex(i)}
            >
              {m.name}{" "}
              <span className="text-gray-500 dark:text-gray-400">
                ({m.id})
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
