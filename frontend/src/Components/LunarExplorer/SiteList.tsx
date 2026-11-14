
import { useState } from "react";

import "./SiteList.css";

export type SiteGroup = {
  key: string;
  title: string;
  note: string;
  items: { id: string; name: string; color: string }[];
  startOpen: boolean;
  // User-made sites: can be renamed, deleted and exported.
  editable?: boolean;
};

type Props = {
  groups: SiteGroup[];
  hiddenIds: Set<string>;
  selectedId: string | null;
  onToggleSite: (id: string) => void;
  onToggleGroup: (ids: string[]) => void;
  onRenameSite: (id: string, name: string) => void;
  onDeleteSite: (id: string) => void;
  onExportGroup: (key: string) => void;
  // "+ Add point": the next click on the map places a custom point.
  addMode: boolean;
  onToggleAddMode: () => void;
};

// Collapsible site menu over the right side of the map, like the Website
// draft's mission menu: clicking a site switches it on or off, and each
// group has a switch for all of its sites.
export default function SiteList({
  groups,
  hiddenIds,
  selectedId,
  onToggleSite,
  onToggleGroup,
  onRenameSite,
  onDeleteSite,
  onExportGroup,
  addMode,
  onToggleAddMode,
}: Props) {
  const [isOpen, setIsOpen] = useState(true);
  const [openGroups, setOpenGroups] = useState(
    () => new Set(groups.filter((group) => group.startOpen).map((group) => group.key))
  );
  // Site being renamed and the text typed so far
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);

  function toggleFold(key: string) {
    const next = new Set(openGroups);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setOpenGroups(next);
  }

  function commitRename() {
    if (editing && editing.name.trim()) onRenameSite(editing.id, editing.name.trim());
    setEditing(null);
  }

  return (
    <aside className={"site-menu" + (isOpen ? "" : " closed")}>
      <button
        type="button"
        className="site-menu-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span>Landing sites</span>
        <span aria-hidden="true">☰</span>
      </button>

      {isOpen && (
        <>
          <button
            type="button"
            className={"site-add" + (addMode ? " active" : "")}
            onClick={onToggleAddMode}
            aria-pressed={addMode}
          >
            {addMode ? "Cancel" : "+ Add point"}
          </button>

          {addMode && (
            <small className="site-add-hint">
              Click the map to place the point (Esc cancels)
            </small>
          )}
        </>
      )}

      {isOpen && groups.map((group) => {
        const ids = group.items.map((item) => item.id);
        const allOn = ids.length > 0 && ids.every((id) => !hiddenIds.has(id));
        const folded = !openGroups.has(group.key);

        return (
          <div className="site-list-group" key={group.key}>
            <div className="site-list-heading">
              <button
                type="button"
                className="site-list-fold"
                onClick={() => toggleFold(group.key)}
                aria-expanded={!folded}
              >
                {folded ? "▸" : "▾"} {group.title}
              </button>

              {group.editable && (
                <button
                  type="button"
                  className="site-list-action"
                  onClick={() => onExportGroup(group.key)}
                  disabled={ids.length === 0}
                  title={`Export ${group.title} points (JSON)`}
                  aria-label={`Export ${group.title} points`}
                >
                  ⤓
                </button>
              )}

              <label className="site-list-switch" title={allOn ? "Turn all off" : "Turn all on"}>
                <input
                  type="checkbox"
                  role="switch"
                  checked={allOn}
                  disabled={ids.length === 0}
                  onChange={() => onToggleGroup(ids)}
                  aria-label={`Show all ${group.title} sites`}
                />
                <span />
              </label>
            </div>

            {!folded && (
              <>
                <small className="site-list-note">{group.note}</small>

                {group.items.map((item) => {
                  const off = hiddenIds.has(item.id);
                  const className =
                    "site-list-item" +
                    (off ? " off" : "") +
                    (item.id === selectedId ? " active" : "");
                  const dot = <i style={{ background: item.color, color: item.color }} />;

                  if (!group.editable) {
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={className}
                        aria-pressed={!off}
                        title={off ? "Turn on" : "Turn off"}
                        onClick={() => onToggleSite(item.id)}
                      >
                        {dot}
                        <span>{item.name}</span>
                      </button>
                    );
                  }

                  // Editable: toggle, rename (✎) and delete (× or the Delete key)
                  return (
                    <div key={item.id} className={className + " editable"}>
                      {editing?.id === item.id ? (
                        <>
                          {dot}
                          <input
                            className="site-list-rename"
                            value={editing.name}
                            autoFocus
                            aria-label="Point name"
                            onChange={(e) => setEditing({ id: item.id, name: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitRename();
                              if (e.key === "Escape") setEditing(null);
                            }}
                            onBlur={commitRename}
                          />
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="site-list-name"
                            aria-pressed={!off}
                            title={off ? "Turn on" : "Turn off"}
                            onClick={() => onToggleSite(item.id)}
                            onKeyDown={(e) => {
                              if (e.key === "Delete") onDeleteSite(item.id);
                            }}
                          >
                            {dot}
                            <span>{item.name}</span>
                          </button>

                          <button
                            type="button"
                            className="site-list-action"
                            onClick={() => setEditing({ id: item.id, name: item.name })}
                            title="Rename"
                            aria-label={`Rename ${item.name}`}
                          >
                            ✎
                          </button>

                          <button
                            type="button"
                            className="site-list-action"
                            onClick={() => onDeleteSite(item.id)}
                            title="Delete"
                            aria-label={`Delete ${item.name}`}
                          >
                            ×
                          </button>
                        </>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        );
      })}
    </aside>
  );
}
