import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";

import type {
  LunarSite,
  SiteTemperatures,
} from "../../types/explorer";

import type {
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

import { LANDING_SITES, isOnPolarMap } from "../../types/sites";
import type { LandingSite } from "../../types/sites";

import { downloadJson } from "../../utils/download";

import SiteInfoCard from "./SiteInfoCard";
import SiteList from "./SiteList";
import type { SiteGroup } from "./SiteList";
import type { CameraPreset, CameraRequest, CameraTarget, GlobeSite } from "./Globe3D";
import "./Globe3D.css";

// CesiumJS is large, so the 3D globe only loads when it is first opened.
const Globe3D = lazy(() => import("./Globe3D"));

type MapView = "2d" | "3d";

type Props = {
  selectedSite: LunarSite | null;
  onSiteSelect: (site: LunarSite) => void;
  onSiteClear: () => void;
  temperature: TemperatureConfig;
  onTemperatureSelection: (stats: TemperatureSelectionStats | null) => void;
};

// Marker sent to the map viewer.
type MapSite = {
  id: string;
  name: string;
  label: string;
  kind: string;
  color: string;
  latitude: number;
  longitude: number;
  region?: [number, number][];
};

const CUSTOM_COLOR = "#ff9f43";

// Artemis III regions share names with craters (Haworth, Nobile, ...) but are
// separate areas next to them, so their map labels say "A3".
const LANDING_MAP_SITES: MapSite[] = LANDING_SITES.filter(isOnPolarMap).map(
  ({ id, name, program, color, latitude, longitude, region }) => ({
    id,
    name,
    label: program === "Artemis" ? `A3 ${name}` : name,
    kind: program === "Artemis" ? "Artemis III region, not the crater" : program,
    color,
    latitude,
    longitude,
    region,
  })
);

function toLunarSite(site: LandingSite): LunarSite {
  return {
    id: site.id,
    name: site.name,
    latitude: site.latitude,
    longitude: site.longitude,
    details: site,
  };
}

// Messages posted by the lunar map viewer (public/lunar-map).
type ViewerMessage =
  | { type: "stamina:viewer-ready" }
  | {
      type: "stamina:site-selected";
      latitude: number;
      longitude: number;
      temperatures: SiteTemperatures;
      elevationM: number | null;
      // Set when a site marker was clicked or focused; absent for a new map point.
      siteId?: string | null;
    }
  | {
      type: "stamina:selection-stats";
      stats: TemperatureSelectionStats | null;
    }
  // The map cancelled "+ Add point" (Esc pressed inside it).
  | { type: "stamina:add-mode"; enabled: boolean };

function isViewerMessage(data: unknown): data is ViewerMessage {
  const type = (data as { type?: unknown } | null)?.type;
  return typeof type === "string" && type.startsWith("stamina:");
}

export default function MapPanel({
  selectedSite,
  onSiteSelect,
  onSiteClear,
  temperature,
  onTemperatureSelection,
}: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [viewerReady, setViewerReady] = useState(false);
  // Site whose info card the user closed; it reopens for the next site.
  const [closedInfoId, setClosedInfoId] = useState<string | null>(null);
  const infoSite = selectedSite?.details;

  // Points clicked on the map ("Custom" group) and sites switched off.
  const [customSites, setCustomSites] = useState<LunarSite[]>([]);
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(() => new Set());
  const customRef = useRef(customSites);
  useEffect(() => {
    customRef.current = customSites;
  }, [customSites]);
  // Numbers new points; never reused, so names stay unique after deletes.
  const nextPointRef = useRef(1);
  // "+ Add point": the next click on empty map places a custom point.
  const [addMode, setAddMode] = useState(false);

  // 2D polar map or 3D globe; the globe stays mounted once opened.
  const [view, setView] = useState<MapView>("2d");
  const [globeOpened, setGlobeOpened] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [cameraRequest, setCameraRequest] = useState<CameraRequest | null>(null);
  const nonceRef = useRef(0);

  function addPoint(latitude: number, longitude: number, values: Partial<LunarSite> = {}) {
    const point: LunarSite = {
      id: `custom-${Date.now()}`,
      name: `Point ${nextPointRef.current++}`,
      latitude,
      longitude,
      ...values,
    };
    customRef.current = [...customRef.current, point];
    setCustomSites(customRef.current);
    setAddMode(false);
    onSiteSelect(point);
  }
  // The message listener below is registered once; it reaches addPoint through a ref.
  const addPointRef = useRef(addPoint);
  useEffect(() => {
    addPointRef.current = addPoint;
  });

  // Messages from the map: readiness, clicked sites and selection area.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if (!isViewerMessage(event.data)) return;

      const message = event.data;

      if (message.type === "stamina:viewer-ready") {
        setViewerReady(true);
      }

      if (
        message.type === "stamina:site-selected" &&
        Number.isFinite(message.latitude) &&
        Number.isFinite(message.longitude)
      ) {
        const { latitude, longitude, temperatures, elevationM, siteId } = message;
        const values = { temperatures, elevationM };
        const named = LANDING_SITES.find((site) => site.id === siteId);
        const custom = customRef.current.find((site) => site.id === siteId);

        if (named) {
          onSiteSelect({ ...toLunarSite(named), ...values });
        } else if (custom) {
          onSiteSelect({ ...custom, ...values });
        } else {
          // A click on empty map ("+ Add point"): keep it as a new custom point.
          addPointRef.current(latitude, longitude, values);
        }
      }

      if (message.type === "stamina:selection-stats") {
        onTemperatureSelection(message.stats);
      }

      if (message.type === "stamina:add-mode") {
        setAddMode(message.enabled);
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onSiteSelect, onTemperatureSelection]);

  function postToViewer(message: object) {
    frameRef.current?.contentWindow?.postMessage(
      message,
      window.location.origin
    );
  }

  // Markers of the sites that are switched on.
  const mapSites = useMemo(() => {
    const custom: MapSite[] = customSites.map((site) => ({
      id: site.id,
      name: site.name,
      label: site.name,
      kind: "custom point",
      color: CUSTOM_COLOR,
      latitude: site.latitude ?? 0,
      longitude: site.longitude ?? 0,
    }));
    return [...LANDING_MAP_SITES, ...custom].filter((site) => !hiddenIds.has(site.id));
  }, [customSites, hiddenIds]);

  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:sites", sites: mapSites });
  }, [viewerReady, mapSites]);

  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:add-mode", enabled: addMode });
  }, [viewerReady, addMode]);

  // Esc cancels "+ Add point" while the focus is in the app.
  useEffect(() => {
    if (!addMode) return;
    function cancel(event: KeyboardEvent) {
      if (event.key === "Escape") setAddMode(false);
    }
    window.addEventListener("keydown", cancel);
    return () => window.removeEventListener("keydown", cancel);
  }, [addMode]);

  // The Temperature filter drives the layer and selection on the map.
  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:temperature-config", config: temperature });
  }, [viewerReady, temperature]);

  // Pin the selected site on the map (the map replies with its values);
  // sites that aren't drawn (Apollo, switched off, none) clear the pin.
  const selectedId = selectedSite?.id ?? null;
  const focusId = mapSites.some((site) => site.id === selectedId) ? selectedId : null;

  useEffect(() => {
    if (viewerReady) postToViewer({ type: "stamina:focus-site", siteId: focusId });
  }, [viewerReady, focusId]);

  // Everything switched on, for the globe: Apollo too (it's off the polar map).
  const globeSites = useMemo<GlobeSite[]>(() => {
    const landing = LANDING_SITES.map(({ id, name, program, color, latitude, longitude, region }) => ({
      id,
      label: program === "Artemis" ? `A3 ${name}` : name,
      color,
      latitude,
      longitude,
      region,
    }));
    const custom = customSites.map((site) => ({
      id: site.id,
      label: site.name,
      color: CUSTOM_COLOR,
      latitude: site.latitude ?? 0,
      longitude: site.longitude ?? 0,
    }));
    return [...landing, ...custom].filter((site) => !hiddenIds.has(site.id));
  }, [customSites, hiddenIds]);

  function switchView(next: MapView) {
    setView(next);
    if (next === "3d") setGlobeOpened(true);
    else setRotating(false);
  }

  function requestCamera(target: CameraTarget) {
    nonceRef.current += 1;
    setCameraRequest({ ...target, nonce: nonceRef.current });
  }

  // Eye button: centre the 2D map on a polar site, otherwise fly the globe to it.
  function goTo(id: string) {
    const onPolarMap =
      LANDING_MAP_SITES.some((site) => site.id === id) ||
      customSites.some((site) => site.id === id && (site.latitude ?? 0) <= -80);

    if (view === "2d" && onPolarMap) {
      postToViewer({ type: "stamina:center-on", siteId: id });
      return;
    }
    switchView("3d");
    requestCamera({ kind: "site", siteId: id });
  }

  // A click on a globe marker selects its site, like the list.
  function pickOnGlobe(id: string) {
    const named = LANDING_SITES.find((site) => site.id === id);
    const custom = customSites.find((site) => site.id === id);
    if (named) onSiteSelect(toLunarSite(named));
    else if (custom) onSiteSelect(custom);
  }

  // Clicking a site switches it on (and selects it) or off.
  function toggleSite(id: string) {
    const next = new Set(hiddenIds);

    if (next.has(id)) {
      next.delete(id);
      const named = LANDING_SITES.find((site) => site.id === id);
      const custom = customSites.find((site) => site.id === id);
      if (named) onSiteSelect(toLunarSite(named));
      else if (custom) onSiteSelect(custom);
    } else {
      next.add(id);
      if (selectedId === id) onSiteClear();
    }

    setHiddenIds(next);
  }

  // Group switch: all off when every site is on, otherwise all on.
  function toggleGroup(ids: string[]) {
    const allOn = ids.every((id) => !hiddenIds.has(id));
    const next = new Set(hiddenIds);
    ids.forEach((id) => (allOn ? next.add(id) : next.delete(id)));
    if (allOn && selectedId && ids.includes(selectedId)) onSiteClear();
    setHiddenIds(next);
  }

  // Custom points: rename, delete, export
  function renameSite(id: string, name: string) {
    setCustomSites((sites) =>
      sites.map((site) => (site.id === id ? { ...site, name } : site))
    );
    if (selectedSite?.id === id) onSiteSelect({ ...selectedSite, name });
  }

  function deleteSite(id: string) {
    setCustomSites((sites) => sites.filter((site) => site.id !== id));
    if (hiddenIds.has(id)) {
      const next = new Set(hiddenIds);
      next.delete(id);
      setHiddenIds(next);
    }
    if (selectedId === id) onSiteClear();
  }

  function exportGroup(key: string) {
    if (key !== "custom") return;

    downloadJson(
      {
        version: 1,
        exportedAt: new Date().toISOString(),
        description:
          "STAMINA custom points. Latitude/longitude in degrees (east-positive), " +
          "elevation in metres relative to 1737.4 km (LOLA), temperatures in kelvin " +
          "(Diviner season summaries, Williams et al. 2019).",
        points: customSites.map((site) => ({
          name: site.name,
          latitude: site.latitude,
          longitude: site.longitude,
          elevationM: site.elevationM ?? null,
          temperaturesK: site.temperatures ?? null,
        })),
      },
      "stamina-custom-points.json"
    );
  }

  const groups: SiteGroup[] = [
    {
      key: "artemis",
      title: "Artemis III",
      note: "A3 regions",
      items: LANDING_SITES.filter((site) => site.program === "Artemis"),
      startOpen: true,
    },
    {
      key: "custom",
      title: "Custom",
      note: "Use + Add point",
      items: customSites.map(({ id, name }) => ({ id, name, color: CUSTOM_COLOR })),
      startOpen: true,
      editable: true,
    },
    {
      key: "apollo",
      title: "Apollo",
      note: "Off the map",
      items: LANDING_SITES.filter((site) => site.program === "Apollo"),
      startOpen: false,
    },
  ];

  return (
    <section className="explorer-map">
      <div className="map-header">
        <strong>{view === "3d" ? "Moon" : "Lunar South Pole"}</strong>
        <span>
          {view === "3d"
            ? "LROC WAC mosaic · Apollo, Artemis III and custom sites"
            : `${temperature.enabled ? "Diviner surface temperature" : "LOLA relief"} · 80°S to the pole`}
        </span>
      </div>

      <div className="map-workspace map-workspace-embed">
        {/* The 2D map stays loaded in 3D: it still supplies site temperatures. */}
        <iframe
          ref={frameRef}
          className={"lunar-map-frame" + (view === "3d" ? " map-view-hidden" : "")}
          src="/lunar-map/index.html?embed=1"
          title="South pole surface temperature map"
        />

        {globeOpened && (
          <div className={view === "3d" ? "" : "map-view-hidden"}>
            <Suspense fallback={<div className="globe-loading">Loading the 3D Moon…</div>}>
              <Globe3D
                sites={globeSites}
                selectedId={selectedId}
                onPick={pickOnGlobe}
                onPlace={(latitude, longitude) => addPoint(latitude, longitude)}
                addMode={addMode && view === "3d"}
                cameraRequest={cameraRequest}
                rotating={rotating && view === "3d"}
              />
            </Suspense>
          </div>
        )}

        <div className="map-switcher" role="group" aria-label="Map view">
          {(["2d", "3d"] as MapView[]).map((option) => (
            <button
              key={option}
              type="button"
              className={view === option ? "active" : ""}
              aria-pressed={view === option}
              onClick={() => switchView(option)}
            >
              <img src={`/globe/thumb_${option}.png`} alt="" />
              {option === "2d" ? "2D pole" : "3D globe"}
            </button>
          ))}
        </div>

        <SiteList
          groups={groups}
          hiddenIds={hiddenIds}
          selectedId={selectedId}
          onToggleSite={toggleSite}
          onToggleGroup={toggleGroup}
          onRenameSite={renameSite}
          onDeleteSite={deleteSite}
          onExportGroup={exportGroup}
          addMode={addMode}
          onToggleAddMode={() => setAddMode(!addMode)}
          onGoTo={goTo}
          view={view}
          rotating={rotating}
          onToggleRotate={() => setRotating(!rotating)}
          onPreset={(preset: CameraPreset) => requestCamera({ kind: "preset", preset })}
        />

        {infoSite && closedInfoId !== infoSite.id && (
          <SiteInfoCard
            site={infoSite}
            onClose={() => setClosedInfoId(infoSite.id)}
          />
        )}
      </div>
    </section>
  );
}
