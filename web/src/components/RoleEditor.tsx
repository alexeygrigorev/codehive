import { useState } from "react";
import { createRole, updateRole } from "@/api/roles";
import type { RoleRead } from "@/api/roles";

interface RoleEditorProps {
  role?: RoleRead;
  onSaved?: () => void;
  onCancel?: () => void;
}

export default function RoleEditor({
  role,
  onSaved,
  onCancel,
}: RoleEditorProps) {
  const isEdit = !!role;

  const [name, setName] = useState(role?.name ?? "");
  const [displayName, setDisplayName] = useState(role?.display_name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [responsibilities, setResponsibilities] = useState(
    role?.responsibilities?.join("\n") ?? "",
  );
  const [allowedTools, setAllowedTools] = useState(
    role?.allowed_tools?.join("\n") ?? "",
  );
  const [deniedTools, setDeniedTools] = useState(
    role?.denied_tools?.join("\n") ?? "",
  );
  const [codingRules, setCodingRules] = useState(
    role?.coding_rules?.join("\n") ?? "",
  );
  const [systemPromptExtra, setSystemPromptExtra] = useState(
    role?.system_prompt_extra ?? "",
  );
  const [submitting, setSubmitting] = useState(false);

  function splitLines(text: string): string[] {
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSubmitting(true);
      if (isEdit) {
        await updateRole(role!.name, {
          display_name: displayName,
          description,
          responsibilities: splitLines(responsibilities),
          allowed_tools: splitLines(allowedTools),
          denied_tools: splitLines(deniedTools),
          coding_rules: splitLines(codingRules),
          system_prompt_extra: systemPromptExtra,
        });
      } else {
        await createRole({
          name,
          display_name: displayName,
          description,
          responsibilities: splitLines(responsibilities),
          allowed_tools: splitLines(allowedTools),
          denied_tools: splitLines(deniedTools),
          coding_rules: splitLines(codingRules),
          system_prompt_extra: systemPromptExtra,
        });
      }
      onSaved?.();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-lg font-semibold">
        {isEdit ? "Edit Role" : "Create Role"}
      </h2>

      <div>
        <label htmlFor="role-name" className="block text-sm font-medium">
          Name
        </label>
        <input
          id="role-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isEdit}
          required
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm disabled:bg-gray-100"
        />
      </div>

      <div>
        <label
          htmlFor="role-display-name"
          className="block text-sm font-medium"
        >
          Display Name
        </label>
        <input
          id="role-display-name"
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="role-description"
          className="block text-sm font-medium"
        >
          Description
        </label>
        <input
          id="role-description"
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="role-responsibilities"
          className="block text-sm font-medium"
        >
          Responsibilities (one per line)
        </label>
        <textarea
          id="role-responsibilities"
          value={responsibilities}
          onChange={(e) => setResponsibilities(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="role-allowed-tools"
          className="block text-sm font-medium"
        >
          Allowed Tools (one per line)
        </label>
        <textarea
          id="role-allowed-tools"
          value={allowedTools}
          onChange={(e) => setAllowedTools(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="role-denied-tools"
          className="block text-sm font-medium"
        >
          Denied Tools (one per line)
        </label>
        <textarea
          id="role-denied-tools"
          value={deniedTools}
          onChange={(e) => setDeniedTools(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="role-coding-rules"
          className="block text-sm font-medium"
        >
          Coding Rules (one per line)
        </label>
        <textarea
          id="role-coding-rules"
          value={codingRules}
          onChange={(e) => setCodingRules(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label
          htmlFor="role-system-prompt-extra"
          className="block text-sm font-medium"
        >
          System Prompt Extra
        </label>
        <textarea
          id="role-system-prompt-extra"
          value={systemPromptExtra}
          onChange={(e) => setSystemPromptExtra(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-blue-500 px-4 py-2 text-sm text-white hover:bg-blue-600 disabled:opacity-50"
        >
          {isEdit ? "Update" : "Create"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
