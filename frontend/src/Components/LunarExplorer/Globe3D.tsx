
import { useEffect, useRef } from "react";

import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import "./Globe3D.css";

// CesiumJS loads workers and assets from here (copied by vite.config.ts).
declare global {
  interface Window {
    CESIUM_BASE_URL?: string;
  }
}
window.CESIUM_BASE_URL = "/cesium/";

// Every position below is on the IAU lunar sphere (1737.4 km), the same
// one the 2D polar map uses, so sites line up in both views.
Cesium.Ellipsoid.default = Cesium.Ellipsoid.MOON;

// LROC WAC global mosaic from NASA Moon Trek: geographic 2x1 tiling at
// level 0, levels 0-8, CORS open (checked against its WMTSCapabilities).
const TREK_WAC_TILES =
  "https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/" +
  "default/default028mm/{TileMatrix}/{TileRow}/{TileCol}.jpg";
// Same mosaic at low resolution, served locally: the base layer when
// Moon Trek is slow or offline (lola_2d/globe_assets.py).
const OFFLINE_BASE = "/globe/lroc_wac_global.jpg";
// Cesium Moon (LOLA/LRO based 3D Tiles) on Cesium ion, used when a token
// is configured in VITE_CESIUM_ION_TOKEN.
const CESIUM_MOON_ASSET_ID = 2684829;
// Polar sites sit within ~150 km of each other; their labels show only once
// the camera is this close (metres), so they don't pile up at the pole.
const POLAR_LABEL_DISTANCE = 1_800_000;

export type GlobeSite = {
  id: string;
  label: string;
  color: string;
  latitude: number;
  longitude: number;
  region?: [number, number][];
};

export type CameraPreset = "nearSide" | "southPole" | "both";

export type CameraTarget =
  | { kind: "site"; siteId: string }
  | { kind: "preset"; preset: CameraPreset };

// The nonce makes a repeated click on the same target fly again.
export type CameraRequest = CameraTarget & { nonce: number };

type Props = {
  sites: GlobeSite[];
  selectedId: string | null;
  onPick: (siteId: string) => void;
  // "+ Add point": the next click on the globe places a custom point there.
  addMode: boolean;
  onPlace: (latitude: number, longitude: number) => void;
  cameraRequest: CameraRequest | null;
  rotating: boolean;
};

const PRESETS: Record<CameraPreset, { lon: number; lat: number; heightKm: number }> = {
  // The near side, where the Apollo sites are.
  nearSide: { lon: 5, lat: 5, heightKm: 4200 },
  // Looking down on the south pole and the Artemis III regions.
  southPole: { lon: 0, lat: -89.9, heightKm: 900 },
  // Near side tilted south: Apollo and the south pole in one view.
  both: { lon: 10, lat: -35, heightKm: 4600 },
};

type Marker = { entity: Cesium.Entity; position: Cesium.Cartesian3 };

const MOON_RADIUS_SQUARED = Cesium.Ellipsoid.MOON.maximumRadius ** 2;

// Markers draw on top of the relief (depth test off), so the ones beyond the
// horizon are hidden here: a surface point P faces a camera at C only when C
// is above P's tangent plane, i.e. P·C > R².
function hideFarSide(viewer: Cesium.Viewer, markers: Marker[]) {
  const camera = viewer.camera.positionWC;
  let changed = false;
  for (const { entity, position } of markers) {
    const visible = Cesium.Cartesian3.dot(position, camera) > MOON_RADIUS_SQUARED;
    if (entity.show !== visible) {
      entity.show = visible;
      changed = true;
    }
  }
  if (changed) viewer.scene.requestRender();
}

function flyTo(viewer: Cesium.Viewer, lon: number, lat: number, heightKm: number) {
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(lon, lat, heightKm * 1000),
    orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 },
    duration: 1.6,
  });
}

export default function Globe3D({
  sites,
  selectedId,
  onPick,
  addMode,
  onPlace,
  cameraRequest,
  rotating,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const markersRef = useRef<Marker[]>([]);
  // The click and render handlers are registered once; they read these refs.
  const onPickRef = useRef(onPick);
  const onPlaceRef = useRef(onPlace);
  const addModeRef = useRef(addMode);
  const rotatingRef = useRef(rotating);

  useEffect(() => {
    onPickRef.current = onPick;
    onPlaceRef.current = onPlace;
    addModeRef.current = addMode;
    rotatingRef.current = rotating;
  }, [onPick, onPlace, addMode, rotating]);

  // Create the globe once.
  useEffect(() => {
    if (!containerRef.current) return;

    const viewer = new Cesium.Viewer(containerRef.current, {
      globe: new Cesium.Globe(Cesium.Ellipsoid.MOON),
      baseLayer: Cesium.ImageryLayer.fromProviderAsync(
        Cesium.SingleTileImageryProvider.fromUrl(OFFLINE_BASE, {
          rectangle: Cesium.Rectangle.MAX_VALUE,
        })
      ),
      skyAtmosphere: false,
      animation: false,
      timeline: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
    });
    viewerRef.current = viewer;

    const { scene } = viewer;
    scene.backgroundColor = Cesium.Color.BLACK;
    scene.fog.enabled = false;
    scene.globe.showGroundAtmosphere = false;
    scene.globe.baseColor = Cesium.Color.fromCssColorString("#2f2f2f");
    // No Earth-sky objects around the Moon
    if (scene.sun) scene.sun.show = false;
    if (scene.moon) scene.moon.show = false;

    viewer.imageryLayers.addImageryProvider(
      new Cesium.WebMapTileServiceImageryProvider({
        url: TREK_WAC_TILES,
        layer: "LRO_WAC_Mosaic_Global_303ppd_v02",
        style: "default",
        format: "image/jpeg",
        tileMatrixSetID: "default028mm",
        tilingScheme: new Cesium.GeographicTilingScheme({ ellipsoid: Cesium.Ellipsoid.MOON }),
        maximumLevel: 8,
        credit: new Cesium.Credit("LROC WAC mosaic: NASA/GSFC/ASU, via NASA Moon Trek"),
      })
    );

    // Optional high-resolution relief from Cesium ion
    const token = import.meta.env.VITE_CESIUM_ION_TOKEN as string | undefined;
    if (token) {
      Cesium.Ion.defaultAccessToken = token;
      Cesium.Cesium3DTileset.fromIonAssetId(CESIUM_MOON_ASSET_ID)
        .then((tileset) => {
          if (viewer.isDestroyed()) return;
          scene.primitives.add(tileset);
          scene.globe.show = false;
        })
        .catch((error) => console.warn("Cesium Moon tileset unavailable:", error));
    }

    const { lon, lat, heightKm } = PRESETS.both;
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, heightKm * 1000),
    });

    // Click on a marker or region selects its site; in "+ Add point" mode a
    // click on the surface places a point there.
    const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
    handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      const picked = scene.pick(click.position);
      const siteId = picked?.id?.properties?.siteId?.getValue();
      if (typeof siteId === "string") {
        onPickRef.current(siteId);
        return;
      }
      if (!addModeRef.current) return;
      const surface = viewer.camera.pickEllipsoid(click.position, Cesium.Ellipsoid.MOON);
      if (!surface) return;
      const { latitude, longitude } = Cesium.Cartographic.fromCartesian(surface, Cesium.Ellipsoid.MOON);
      onPlaceRef.current(Cesium.Math.toDegrees(latitude), Cesium.Math.toDegrees(longitude));
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Slow spin around the lunar axis while "Rotate" is on.
    let last = performance.now();
    const spin = () => {
      const now = performance.now();
      if (rotatingRef.current) {
        viewer.camera.rotate(Cesium.Cartesian3.UNIT_Z, -Cesium.Math.toRadians(6) * ((now - last) / 1000));
      }
      last = now;
    };
    scene.preRender.addEventListener(spin);

    // The clock ticks every animation frame (also in request-render mode),
    // so far-side markers hide as soon as the camera moves.
    viewer.clock.onTick.addEventListener(() => hideFarSide(viewer, markersRef.current));

    return () => {
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // Crosshair cursor while placing a point
  useEffect(() => {
    containerRef.current?.classList.toggle("adding", addMode);
  }, [addMode]);

  // Keep the request-render loop running while spinning.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer) viewer.scene.requestRenderMode = !rotating;
  }, [rotating]);

  // Site markers, labels and Artemis region outlines.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    viewer.entities.removeAll();
    const markers: Marker[] = [];
    for (const site of sites) {
      const selected = site.id === selectedId;
      const color = Cesium.Color.fromCssColorString(site.color);
      const properties = { siteId: site.id };
      const polarLabel = site.latitude < -75 && !selected;

      const position = Cesium.Cartesian3.fromDegrees(site.longitude, site.latitude);
      const marker = viewer.entities.add({
        id: site.id,
        position,
        properties,
        point: {
          pixelSize: selected ? 13 : 9,
          color,
          outlineColor: selected ? Cesium.Color.CYAN : Cesium.Color.BLACK,
          outlineWidth: selected ? 3 : 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: site.label,
          font: "600 13px system-ui, sans-serif",
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
          verticalOrigin: Cesium.VerticalOrigin.CENTER,
          pixelOffset: new Cesium.Cartesian2(10, 0),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: polarLabel
            ? new Cesium.DistanceDisplayCondition(0, POLAR_LABEL_DISTANCE)
            : undefined,
        },
      });
      markers.push({ entity: marker, position });

      if (site.region) {
        const ring = site.region.flatMap(([lat, lon]) => [lon, lat]);
        viewer.entities.add({
          id: `${site.id}:region`,
          properties,
          polygon: {
            hierarchy: Cesium.Cartesian3.fromDegreesArray(ring),
            material: (selected ? Cesium.Color.CYAN : Cesium.Color.WHITE).withAlpha(selected ? 0.3 : 0.15),
            classificationType: Cesium.ClassificationType.BOTH,
          },
        });
      }
    }
    markersRef.current = markers;
    hideFarSide(viewer, markers);
    viewer.scene.requestRender();
  }, [sites, selectedId]);

  // "Go to" (eye) and the camera presets
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !cameraRequest) return;

    if (cameraRequest.kind === "preset") {
      const { lon, lat, heightKm } = PRESETS[cameraRequest.preset];
      flyTo(viewer, lon, lat, heightKm);
      return;
    }
    const site = sites.find((item) => item.id === cameraRequest.siteId);
    // Polar sites sit close together, so they get a closer view.
    if (site) flyTo(viewer, site.longitude, site.latitude, site.latitude < -80 ? 220 : 1200);
    // The request object changes on every click; sites don't need to re-trigger it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraRequest]);

  return <div className="globe-3d" ref={containerRef} />;
}
