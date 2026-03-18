import { useState } from "react";
import RoleList from "@/components/RoleList";
import RoleEditor from "@/components/RoleEditor";
import type { RoleRead } from "@/api/roles";

type Mode = "list" | "create" | "edit";

export default function RolesPage() {
  const [mode, setMode] = useState<Mode>("list");
  const [editingRole, setEditingRole] = useState<RoleRead | undefined>();
  const [key, setKey] = useState(0);

  function handleEdit(role: RoleRead) {
    setEditingRole(role);
    setMode("edit");
  }

  function handleCreate() {
    setEditingRole(undefined);
    setMode("create");
  }

  function handleSaved() {
    setMode("list");
    setEditingRole(undefined);
    setKey((k) => k + 1);
  }

  function handleCancel() {
    setMode("list");
    setEditingRole(undefined);
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold dark:text-gray-100">Roles</h1>
      {mode === "list" && (
        <RoleList key={key} onEdit={handleEdit} onCreate={handleCreate} />
      )}
      {(mode === "create" || mode === "edit") && (
        <RoleEditor
          role={editingRole}
          onSaved={handleSaved}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}
