import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { apiErrorMessage } from "../../services/apiError";

import type {
  FilterStates,
  LunarSite,
  SiteTemperatures,
} from "../../types/explorer";

import type {
  TemperatureConfig,
  TemperatureSelectionStats,
} from "../../types/temperature";

import { COMPARE_LIMIT, LANDING_SITES, isOnPolarMap } from "../../types/sites";
import type { CompareSite, LandingSite, VisiblePolarSite, InitialMapSite } from "../../types/sites";
import CircularSiteMap from "./CircularSiteMap";

import { downloadJson } from "../../utils/download";

import type { BodyPositions } from "./MapTimeline";

import SiteInfoCard from "./SiteInfoCard";
import SiteList from "./SiteList";
import type { SiteGroup } from "./SiteList";
import type { CameraPreset, CameraRequest, CameraTarget, GlobeSite } from "./Globe3D";
import "./Globe3D.css";

// CesiumJS is large, so the 3D globe only loads when it is first opened.
const Globe3D = lazy(() => import("./Globe3D"));

type MapView = "2d" | "3d";

// Crop sizes for the comparison cells (side of the square, km)
const CROP_SIZES_KM = [10, 20, 40, 80];

type Props = {
  initialSite?: InitialMapSite;
  onMapArea: () => void;
  date: string;
  positions: BodyPositions | null;
  onVisibilityReady?: (ready: boolean) => void;
  playing?: boolean;
  selectedSite: LunarSite | null;
  // Built-in filters: the terrain overlay and the Sun/Earth terrain visibility masks act on the map.
  filters: FilterStates;
  onSiteSelect: (site: LunarSite) => void;
  onSiteClear: () => void;
  temperature: TemperatureConfig;
  onTemperatureSelection: (stats: TemperatureSelectionStats | null) => void;
  // Comparison grid (opened from the inspector's Compare button)
  comparing: boolean;
  onCompareClose: () => void;
  onCompareSitesChange: (sites: CompareSite[]) => void;
  onVisibleSitesChange?: (sites: VisiblePolarSite[]) => void;
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
type VisibilityMask = { size: number; radiusM: number; resolutionM: number; coveragePct: number; encoding: "bitset-msb"; visiblePacked: string; coveragePacked: string };
type TerrainOverlay = { size: number; radiusM: number; coveragePct: number; shadePacked: string; coveragePacked: string };

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
  initialSite,
  onMapArea,
  positions,
  onVisibilityReady,
  playing = false,
  selectedSite,
  filters,
  onSiteSelect,
  onSiteClear,
  temperature,
  onTemperatureSelection,
  comparing,
  onCompareClose,
  onCompareSitesChange,
  onVisibleSitesChange,
}: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [viewerReady, setViewerReady] = useState(false);
  const [visibilityMask, setVisibilityMask] = useState<VisibilityMask | null>(null);
  const [terrainOverlay, setTerrainOverlay] = useState<TerrainOverlay | null>(null);
  const [mapCenter, setMapCenter] = useState<{ id: string; latitude: number; longitude: number; name: string } | null>(initialSite ? { ...initialSite, id: "initial-site" } : null);
  const globalCentered = mapCenter !== null;
  const globalMapActive = globalCentered && !comparing;
  const sunVisible = Boolean(filters.sunVisibility?.enabled);
  const earthVisible = Boolean(filters.earthVisibility?.enabled);
  const terrainEnabled = Boolean(filters.terrain?.enabled);
  useEffect(() => {
    if (viewerReady && !globalMapActive) postToViewer({ type: "stamina:terrain-overlay", enabled: terrainEnabled });
  }, [viewerReady, terrainEnabled, globalMapActive]);
  useEffect(() => {
    if (!viewerReady && !globalMapActive) return;
    if (!sunVisible && !earthVisible) {
      onVisibilityReady?.(true);
      setVisibilityMask(null);
      if (viewerReady) postToViewer({ type: "stamina:visibility-mask", config: null });
      return;
    }
    const controller = new AbortController();
    onVisibilityReady?.(false);
    setVisibilityMask(null);
    if (viewerReady && !globalMapActive) postToViewer({ type: "stamina:visibility-mask", config: { pending: true } });
    const timer = window.setTimeout(async () => {
      if (!positions) return;
      try {
        // Show a quick result, then refine without blanking the preview.
        for (const size of playing ? [768] : [384, 1536]) {
          if (controller.signal.aborted) return;
          const response = await fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/visibility-map`, {
            method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
            body: JSON.stringify({ sun: sunVisible ? positions.sun : null, earth: earthVisible ? positions.earth : null, size, encoding: "bitset",
              ...(globalMapActive && mapCenter ? { center: [mapCenter.latitude, mapCenter.longitude] } : {}) }),
          });
          const data = await response.json();
          if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
          if (!Number.isInteger(data.size) || data.size < 32 || data.size > size || data.encoding !== "bitset-msb" ||
            typeof data.visiblePacked !== "string" || atob(data.visiblePacked).length !== Math.ceil(data.size*data.size/8) ||
            typeof data.coveragePacked !== "string" || atob(data.coveragePacked).length !== Math.ceil(data.size*data.size/8)) throw new Error("Incomplete visibility map.");
          if (controller.signal.aborted) return;
          if (globalMapActive && data.coveragePct === 0) throw new Error("NASA global LOLA returned no terrain for this map center.");
          if (globalMapActive) setVisibilityMask(data as VisibilityMask);
          else postToViewer({ type: "stamina:visibility-mask", config: data });
        }
        onVisibilityReady?.(true);
      } catch (cause) {
        if (!controller.signal.aborted) console.error("Visibility map unavailable:", cause);
      }
    }, 150);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [viewerReady, positions, sunVisible, earthVisible, onVisibilityReady, playing, globalMapActive, mapCenter]);
  // Site whose info card the user closed; it reopens for the next site.
  const [closedInfoId, setClosedInfoId] = useState<string | null>(null);
  const infoSite = selectedSite?.details;

  // Points clicked on the map ("Custom" group) and sites switched off.
  const [customSites, setCustomSites] = useState<LunarSite[]>(initialSite ? [{ ...initialSite, id: "initial-site" }] : []);
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(() => new Set(initialSite ? LANDING_SITES.map(site => site.id) : []));
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
  // The comparison grid replaces the map with 2D cells, so it shows the 2D view.
  const activeView: MapView = comparing ? "2d" : view;

  useEffect(() => {
    if (!terrainEnabled || !globalMapActive || activeView !== "2d" || !mapCenter) {
      setTerrainOverlay(null);
      return;
    }
    const controller = new AbortController();
    setTerrainOverlay(null);
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/terrain-map`, {
          method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
          body: JSON.stringify({ center: [mapCenter.latitude, mapCenter.longitude], size: 768 }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
        const expected = Math.ceil(data.size*data.size/8);
        if (!Number.isInteger(data.size) || data.size < 128 || data.size > 1024 ||
          typeof data.shadePacked !== "string" || atob(data.shadePacked).length !== data.size*data.size ||
          typeof data.coveragePacked !== "string" || atob(data.coveragePacked).length !== expected) {
          throw new Error("Incomplete terrain overlay.");
        }
        if (!controller.signal.aborted) setTerrainOverlay(data as TerrainOverlay);
      } catch (cause) {
        if (!controller.signal.aborted) console.error("Terrain overlay unavailable:", cause);
      }
    }, 100);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [terrainEnabled, globalMapActive, activeView, mapCenter]);

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
    return point;
  }
  // "Add by coordinates": validates, normalises the longitude and adds the point.
  function addPointAt(latitude: number, longitude: number, name: string, centerMap: boolean): string | null {
    if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
      return "Latitude must be between -90 and 90.";
    }
    if (!Number.isFinite(longitude) || longitude < -180 || longitude > 360) {
      return "Longitude must be between -180 and 360.";
    }
    const lon = longitude > 180 ? longitude - 360 : longitude;
    const point = addPoint(latitude, lon, name ? { name } : {});
    if (centerMap) centerOn2D(point);
    return null;
  }

  // The message listener below is registered once; it reaches addPoint through a ref.
  const addPointRef = useRef(addPoint);
  useEffect(() => {
    addPointRef.current = addPoint;
  });

  // Messages from the map: readiness, clicked sites and selection area.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin || event.source !== frameRef.current?.contentWindow) return;
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

  // Share the menu's enabled polar sites with the visibility timelines too.
  const visiblePolarSites = useMemo<VisiblePolarSite[]>(() => mapSites
    .filter(site => site.latitude <= -80)
    .map(({ id, name, latitude, longitude }) => ({ id, name, latitude, longitude })), [mapSites]);
  useEffect(() => {
    onVisibleSitesChange?.(visiblePolarSites);
  }, [visiblePolarSites, onVisibleSitesChange]);

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

  // Comparison: the switched-on sites inside the polar map, at most COMPARE_LIMIT shown.
  const [cropKm, setCropKm] = useState(80);
  const [menuOpen, setMenuOpen] = useState(true);
  const compareSites = useMemo<CompareSite[]>(
    () => mapSites
      .filter((site) => site.latitude <= -80)
      .map(({ id, name }) => ({ id, name })),
    [mapSites]
  );
  const comparedIds = compareSites.slice(0, COMPARE_LIMIT).map((site) => site.id);

  useEffect(() => {
    onCompareSitesChange(compareSites);
  }, [compareSites, onCompareSitesChange]);


  const comparedKey = comparedIds.join(",");
  useEffect(() => {
    if (!viewerReady) return;
    postToViewer({
      type: "stamina:compare",
      compare: comparing
        ? {
            siteIds: comparedKey.split(","),
            halfSizeM: cropKm * 500,
            // Keep the cells clear of the site menu over the right edge
            insetRight: menuOpen ? 196 : 0,
          }
        : null,
    });
  }, [viewerReady, comparing, comparedKey, cropKm, menuOpen]);

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

  function centerOn2D(site: LunarSite) {
    if (site.latitude == null || site.longitude == null) return;
    setMapCenter({ id: site.id, latitude: site.latitude, longitude: site.longitude, name: site.name });
    setView("2d");
    setRotating(false);
    if (comparing) onCompareClose();
  }

  function defaultMap() {
    setMapCenter(null);
    setView("2d");
    setRotating(false);
    if (comparing) onCompareClose();
    if (viewerReady) postToViewer({ type: "stamina:default-view" });
  }

  // Eye button: keep the current dimensional view and center it on the site.
  function goTo(id: string) {
    if (activeView === "2d") {
      const site = LANDING_SITES.find(site => site.id === id) ?? customSites.find(site => site.id === id);
      if (site) centerOn2D(site);
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
    if (mapCenter?.id === id) setMapCenter({ ...mapCenter, name });
    setCustomSites((sites) =>
      sites.map((site) => (site.id === id ? { ...site, name } : site))
    );
    if (selectedSite?.id === id) onSiteSelect({ ...selectedSite, name });
  }

  function deleteSite(id: string) {
    if (mapCenter?.id === id) defaultMap();
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
        {comparing ? (
          <>
            <strong>
              Comparing {comparedIds.length} site{comparedIds.length === 1 ? "" : "s"}
            </strong>
            <span className="compare-controls">
              {compareSites.length > COMPARE_LIMIT &&
                `First ${COMPARE_LIMIT} of ${compareSites.length} · `}
              <label>
                Crop{" "}
                <select value={cropKm} onChange={(e) => setCropKm(Number(e.target.value))}>
                  {CROP_SIZES_KM.map((km) => (
                    <option key={km} value={km}>{km} × {km} km</option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={onCompareClose}>Close ✕</button>
            </span>
          </>
        ) : (
          <>
            <strong>{activeView === "3d" ? "Moon" : mapCenter ? mapCenter.name : "Lunar South Pole"}</strong>
            <span>
              {activeView === "3d"
                ? "LROC WAC mosaic · Apollo, Artemis III and custom sites"
                : globalCentered ? `LROC WAC imagery | centered at ${mapCenter.latitude.toFixed(3)}°, ${mapCenter.longitude.toFixed(3)}°`
                : `${temperature.enabled ? "Diviner surface temperature" : "LOLA relief"}${mapCenter ? " | site-centered 2D" : " · 80°S to the pole"}`}
            </span>
            <div className="map-center-actions">
              <button type="button" disabled={selectedSite?.latitude == null || selectedSite.longitude == null} onClick={() => selectedSite && centerOn2D(selectedSite)}>Center 2D on selected site</button>
              {mapCenter && <button type="button" onClick={defaultMap}>Default south pole</button>}
            </div>
          </>
        )}
      </div>

      <div className="map-workspace map-workspace-embed">
        {!comparing && <button className="map-area-button" type="button" onClick={onMapArea} aria-haspopup="dialog" title="Choose coordinates or use the default south-pole map">Map area</button>}
        {/* The 2D map stays loaded in 3D: it still supplies site temperatures. */}
        <iframe
          ref={frameRef}
          className={"lunar-map-frame" + (activeView === "3d" || (globalCentered && !comparing) ? " map-view-hidden" : "")}
          src="/lunar-map/index.html?embed=1"
          title="South pole surface temperature map"
        />

        {globalCentered && !comparing && activeView === "2d" && (
            <CircularSiteMap key={mapCenter.id} center={mapCenter} sites={globeSites} selectedId={selectedId} visibilityMask={visibilityMask} terrainOverlay={terrainOverlay}
              onPick={pickOnGlobe} onPlace={(latitude, longitude) => addPoint(latitude, longitude)}
              addMode={addMode} />
        )}

        {globeOpened && (
          <div className={activeView === "3d" ? "" : "map-view-hidden"}>
            <Suspense fallback={<div className="globe-loading">Loading the 3D Moon…</div>}>
              <Globe3D
                sites={globeSites}
                selectedId={selectedId}
                onPick={pickOnGlobe}
                onPlace={(latitude, longitude) => addPoint(latitude, longitude)}
                addMode={addMode && activeView === "3d"}
                cameraRequest={cameraRequest}
                rotating={rotating && activeView === "3d"}
              />
            </Suspense>
          </div>
        )}

        {!comparing && <div className="map-switcher" role="group" aria-label="Map view">
          {(["2d", "3d"] as MapView[]).map((option) => (
            <button
              key={option}
              type="button"
              className={activeView === option ? "active" : ""}
              aria-pressed={activeView === option}
              onClick={() => switchView(option)}
            >
              <img src={`/globe/thumb_${option}.png`} alt="" />
              {option === "2d" ? mapCenter ? "2D site" : "2D pole" : "3D globe"}
            </button>
          ))}
        </div>}

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
          onAddCoordinates={addPointAt}
          onGoTo={goTo}
          view={activeView}
          rotating={rotating}
          onToggleRotate={() => setRotating(!rotating)}
          onPreset={(preset: CameraPreset) => requestCamera({ kind: "preset", preset })}
          onOpenChange={setMenuOpen}
        />

        {infoSite && closedInfoId !== infoSite.id && !comparing && (
          <SiteInfoCard
            site={infoSite}
            onClose={() => setClosedInfoId(infoSite.id)}
          />
        )}
      </div>

    </section>
  );
}
