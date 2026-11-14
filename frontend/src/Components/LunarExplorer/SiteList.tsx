
import { useState } from "react";

import { LANDING_SITES, isOnPolarMap } from "../../types/sites";
import type { LandingSite } from "../../types/sites";

import "./SiteList.css";

type Props = {
  selectedId: string | null;
  onSelect: (site: LandingSite) => void;
};

const GROUPS = [
  {
    title: "Artemis III",
    note: "On the map",
    sites: LANDING_SITES.filter(isOnPolarMap),
    startOpen: true,
  },
  {
    title: "Apollo",
    note: "Off the map",
    sites: LANDING_SITES.filter((site) => !isOnPolarMap(site)),
    startOpen: false,
  },
];

// Collapsible site menu over the right side of the map, like the
// Website draft's mission menu.
export default function SiteList({ selectedId, onSelect }: Props) {
  const [isOpen, setIsOpen] = useState(true);
  // Group titles fold their lists; Apollo starts folded (not on the polar map).
  const [openGroups, setOpenGroups] = useState(
    () => new Set(GROUPS.filter((group) => group.startOpen).map((group) => group.title))
  );

  function toggleGroup(title: string) {
    const next = new Set(openGroups);
    if (next.has(title)) next.delete(title);
    else next.add(title);
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

      {isOpen && GROUPS.map((group) => (
        <div className="site-list-group" key={group.title}>
          <button
            type="button"
            className="site-list-heading"
            onClick={() => toggleGroup(group.title)}
            aria-expanded={openGroups.has(group.title)}
          >
            <span>
              {openGroups.has(group.title) ? "▾" : "▸"} {group.title}
            </span>
            <small>{group.note}</small>
          </button>

          {openGroups.has(group.title) && group.sites.map((site) => (
            <button
              key={site.id}
              type="button"
              className={
                "site-list-item" +
                (site.id === selectedId ? " active" : "")
              }
              aria-pressed={site.id === selectedId}
              onClick={() => onSelect(site)}
            >
              <i style={{ background: site.color, color: site.color }} />
              <span>{site.name}</span>
            </button>
          ))}
        </div>
      ))}
    </aside>
  );
}
