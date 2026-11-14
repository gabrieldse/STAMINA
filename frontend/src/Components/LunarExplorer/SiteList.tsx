
import { useState } from "react";

import "./SiteList.css";

export type SiteGroup = {
  key: string;
  title: string;
  note: string;
  items: { id: string; name: string; color: string }[];
  startOpen: boolean;
};

type Props = {
  groups: SiteGroup[];
  hiddenIds: Set<string>;
  selectedId: string | null;
  onToggleSite: (id: string) => void;
  onToggleGroup: (ids: string[]) => void;
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
}: Props) {
  const [isOpen, setIsOpen] = useState(true);
  const [openGroups, setOpenGroups] = useState(
    () => new Set(groups.filter((group) => group.startOpen).map((group) => group.key))
  );

  function toggleFold(key: string) {
    const next = new Set(openGroups);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setOpenGroups(next);
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
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={
                        "site-list-item" +
                        (off ? " off" : "") +
                        (item.id === selectedId ? " active" : "")
                      }
                      aria-pressed={!off}
                      title={off ? "Turn on" : "Turn off"}
                      onClick={() => onToggleSite(item.id)}
                    >
                      <i style={{ background: item.color, color: item.color }} />
                      <span>{item.name}</span>
                    </button>
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
