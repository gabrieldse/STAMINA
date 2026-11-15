
import { useState } from "react";

import type { CameraPreset } from "./Globe3D";

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
  // Adds a custom point at typed coordinates; returns an error message or null.
  onAddCoordinates: (latitude: number, longitude: number, name: string) => string | null;
  // Eye button: move the view to the site.
  onGoTo: (id: string) => void;
  // 3D globe controls
  view: "2d" | "3d";
  rotating: boolean;
  onToggleRotate: () => void;
  onPreset: (preset: CameraPreset) => void;
  // Lets the comparison grid keep clear of the open menu
  onOpenChange?: (open: boolean) => void;
};

const PRESET_BUTTONS: { preset: CameraPreset; label: string; title: string }[] = [
  { preset: "nearSide", label: "Near side", title: "The near side, with the Apollo sites" },
  { preset: "southPole", label: "South pole", title: "Look down on the south pole and the Artemis III regions" },
  { preset: "both", label: "Both", title: "Near side tilted south: Apollo and the south pole together" },
];

// Collapsible site menu over the right side of the map, like the Website
// draft's mission menu: clicking a site switches it on or off, the eye moves
// the view to it, and each group has a switch for all of its sites.
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
  onAddCoordinates,
  onGoTo,
  view,
  rotating,
  onToggleRotate,
  onPreset,
  onOpenChange,
}: Props) {
  // Starts folded; MapPanel's menuOpen mirrors this default.
  const [isOpen, setIsOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState(
    () => new Set(groups.filter((group) => group.startOpen).map((group) => group.key))
  );
  // Site being renamed and the text typed so far
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);
  // "Add by coordinates" form
  const [coordsOpen, setCoordsOpen] = useState(false);
  const [coords, setCoords] = useState({ lat: "", lon: "", name: "" });
  const [coordsError, setCoordsError] = useState("");

  function submitCoordinates() {
    const latitude = Number(coords.lat), longitude = Number(coords.lon);
    if (coords.lat.trim() === "" || coords.lon.trim() === "") {
      setCoordsError("Enter both latitude and longitude.");
      return;
    }
    const error = onAddCoordinates(latitude, longitude, coords.name.trim());
    setCoordsError(error ?? "");
    if (!error) {
      setCoords({ lat: "", lon: "", name: "" });
      setCoordsOpen(false);
    }
  }

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
        onClick={() => {
          setIsOpen(!isOpen);
          onOpenChange?.(!isOpen);
        }}
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

          <button
            type="button"
            className={"site-add site-add-coords" + (coordsOpen ? " active" : "")}
            onClick={() => {
              setCoordsOpen(!coordsOpen);
              setCoordsError("");
            }}
            aria-expanded={coordsOpen}
          >
            ⌖ Add by coordinates
          </button>

          {coordsOpen && (
            <form
              className="site-coords"
              // Our own messages, the same in every browser
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                submitCoordinates();
              }}
            >
              <div className="site-coords-row">
                <label>
                  Lat °
                  <input
                    type="number"
                    step="any"
                    min={-90}
                    max={90}
                    placeholder="-86.8"
                    value={coords.lat}
                    onChange={(e) => setCoords({ ...coords, lat: e.target.value })}
                    autoFocus
                  />
                </label>
                <label>
                  Lon °
                  <input
                    type="number"
                    step="any"
                    min={-180}
                    max={360}
                    placeholder="-22.8"
                    value={coords.lon}
                    onChange={(e) => setCoords({ ...coords, lon: e.target.value })}
                  />
                </label>
              </div>
              <input
                type="text"
                maxLength={60}
                placeholder="Name (optional)"
                aria-label="Point name (optional)"
                value={coords.name}
                onChange={(e) => setCoords({ ...coords, name: e.target.value })}
              />
              <small className="site-coords-hint">
                Degrees, north and east positive. South of 80°S shows on the 2D map.
              </small>
              {coordsError && <small className="site-coords-error" role="alert">{coordsError}</small>}
              <button type="submit" className="site-coords-submit">Add point</button>
            </form>
          )}

          {view === "3d" && (
            <div className="site-globe-controls">
              <button
                type="button"
                className={"site-rotate" + (rotating ? " active" : "")}
                onClick={onToggleRotate}
                aria-pressed={rotating}
              >
                {rotating ? "■ Stop rotation" : "⟳ Rotate globe"}
              </button>

              <div className="site-presets" role="group" aria-label="Camera views">
                {PRESET_BUTTONS.map(({ preset, label, title }) => (
                  <button key={preset} type="button" title={title} onClick={() => onPreset(preset)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
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
                  const dot = <i style={{ background: item.color, color: item.color }} />;

                  // Row: toggle (name), go to (eye), and for custom points
                  // rename (✎) and delete (× or the Delete key).
                  return (
                    <div
                      key={item.id}
                      className={
                        "site-list-item" +
                        (off ? " off" : "") +
                        (item.id === selectedId ? " active" : "")
                      }
                    >
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
                              if (group.editable && e.key === "Delete") onDeleteSite(item.id);
                            }}
                          >
                            {dot}
                            <span>{item.name}</span>
                          </button>

                          <button
                            type="button"
                            className="site-list-action site-list-eye"
                            onClick={() => onGoTo(item.id)}
                            title="Go to"
                            aria-label={`Go to ${item.name}`}
                          >
                            👁
                          </button>

                          {group.editable && (
                            <>
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
