"""Local SPICE-based, geometric horizon analysis API."""
from datetime import date, timedelta, datetime, timezone
from datetime import date as CalendarDate
from threading import Lock
from typing import Literal

import numpy as np
import spiceypy as sp
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from backend.horizon import body_visibility, profile
from backend.visibility_map import terrain_overlay_map, visibility_map
from backend.visibility_kernel import NUMBA_AVAILABLE
from SMEData.kernel_loaders import load_kernels
from backend.custom_filter_engine import CustomFilterRule, evaluate_custom_filters

app = FastAPI()
SPICE_LOCK = Lock()


@app.get("/api/health")
def health():
    """Lightweight readiness check used before the launcher opens a browser."""
    return {"application": "STAMINA", "status": "ready"}


class VisibilityMapRequest(BaseModel):
    sun: list[float] | None = Field(default=None, min_length=3, max_length=3)
    earth: list[float] | None = Field(default=None, min_length=3, max_length=3)
    center: list[float] = Field(default_factory=lambda: [-90.0, 0.0], min_length=2, max_length=2)
    size: int = Field(default=768, ge=32, le=2048, strict=True)
    encoding: Literal["array", "bitset"] = "array"


class TerrainMapRequest(BaseModel):
    center: list[float] = Field(min_length=2, max_length=2)
    size: int = Field(default=768, ge=128, le=1024, strict=True)


@app.post("/api/terrain-map")
def map_terrain(request: TerrainMapRequest):
    if not np.isfinite(request.center).all() or not -90 <= request.center[0] <= 90 or not -180 <= request.center[1] <= 360:
        raise HTTPException(422, "Invalid map center coordinates.")
    center = (request.center[0], ((request.center[1]+180)%360)-180)
    try:
        return terrain_overlay_map(request.size, center)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/visibility-map")
def map_visibility(request: VisibilityMapRequest):
    if request.sun is None and request.earth is None:
        raise HTTPException(422, "Select Sun or Earth visibility.")
    for vector in (request.sun, request.earth):
        if vector is not None and (not np.isfinite(vector).all() or np.linalg.norm(vector) <= 1740):
            raise HTTPException(422, "Invalid Moon-fixed body position.")
    if not np.isfinite(request.center).all() or not -90 <= request.center[0] <= 90 or not -180 <= request.center[1] <= 360:
        raise HTTPException(422, "Invalid map center coordinates.")
    try:
        # Keep installations without the optional compiler responsive too.
        size = request.size if NUMBA_AVAILABLE else min(request.size, 512)
        center = (request.center[0], ((request.center[1]+180)%360)-180)
        if center == (-90.0, 0.0):
            return visibility_map(size, tuple(request.sun) if request.sun else None,
                                  tuple(request.earth) if request.earth else None, request.encoding)
        return visibility_map(size, tuple(request.sun) if request.sun else None,
                              tuple(request.earth) if request.earth else None, request.encoding, center)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/position-timeline")
def position_timeline(date: date, durationDays: int = Query(default=14, ge=1, le=365)):
    """Hourly Moon-fixed body centers, including both mission endpoints."""
    end = date + timedelta(days=durationDays)
    if date < CalendarDate(1850, 1, 1) or end > CalendarDate(2150, 1, 1):
        raise HTTPException(422, "Choose a mission entirely between 1850 and 2150.")
    with SPICE_LOCK:
        try:
            load_kernels()
            start = datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
            stamps = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
                      for i in range(durationDays * 24 + 1)]
            times = np.array([sp.str2et(stamp) for stamp in stamps])
            vectors = {body.lower(): np.asarray(sp.spkpos(body, times, "IAU_MOON", "NONE", "MOON")[0]).tolist()
                       for body in ["SUN", "EARTH"]}
            return dict(times=stamps, **vectors)
        except sp.utils.exceptions.SpiceyError as exc:
            raise HTTPException(503, "Ephemeris unavailable for this mission.") from exc


@app.get("/api/positions")
def positions(date: date):
    """Body centers in Moon-fixed kilometres at mission start (00:00 UTC)."""
    if not CalendarDate(1850, 1, 1) <= date <= CalendarDate(2150, 1, 1):
        raise HTTPException(422, "Choose a date between 1850 and 2150.")
    with SPICE_LOCK:
        try:
            load_kernels()
            et = sp.str2et(date.isoformat() + "T00:00:00")
            vectors = {body.lower(): sp.spkpos(body, et, "IAU_MOON", "NONE", "MOON")[0].tolist()
                       for body in ["SUN", "EARTH"]}
            return dict(**vectors, utc=date.isoformat() + "T00:00:00Z")
        except sp.utils.exceptions.SpiceyError as exc:
            raise HTTPException(503, "Ephemeris unavailable for this date.") from exc


class Site(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sunVisibility: bool = True
    earthVisibility: bool = True
    terrain: bool = False
    analysisMode: str = Field(default="period", pattern="^(instant|period)$")


class AnalysisRequest(BaseModel):
    site: Site
    date: date
    durationDays: int = Field(ge=1, le=365, strict=True)
    filters: Filters = Field(default_factory=Filters)
    customFilters: list[CustomFilterRule] = Field(default_factory=list, max_length=100)


def longest_outage(visible, step_hours):
    longest = current = 0
    for value in visible:
        current = 0 if value else current + 1
        longest = max(longest, current)
    return round(longest * step_hours, 2)


def visibility_segments(values):
    """Lossless runs of samples, with exclusive end indices."""
    starts = [0] + (np.flatnonzero(values[1:] != values[:-1]) + 1).tolist()
    ends = starts[1:] + [len(values)]
    return [dict(start=a, end=b, visible=bool(values[a])) for a, b in zip(starts, ends)]


@app.post("/api/analyze")
def analyze(request: AnalysisRequest):
    instant = request.filters.analysisMode == "instant"
    end = request.date + timedelta(days=0 if instant else request.durationDays)
    if request.date < date(1850, 1, 1) or end > date(2150, 1, 1):
        raise HTTPException(422, "Choose a mission entirely between 1850-01-01 and 2150-01-01 (ephemeris coverage).")
    # SPICE's kernel pool is process-global and must not be used concurrently.
    with SPICE_LOCK:
        try:
            load_kernels()
            start = sp.str2et(request.date.isoformat() + "T00:00:00")
            stop = sp.str2et(end.isoformat() + "T00:00:00")
            count = 1 if instant else request.durationDays * 24 * 6
            step = 0 if instant else (stop - start) / count
            times = np.array([start]) if instant else start + (np.arange(count) + .5) * step
            visibility = []
            for body in ["SUN", "EARTH"]:
                positions, _ = sp.spkpos(body, times, "IAU_MOON", "NONE", "MOON")
                visibility.append(body_visibility(positions, request.site.latitude, request.site.longitude))
        except ValueError as exc:
            raise HTTPException(503, str(exc)) from exc
        except sp.utils.exceptions.SpiceyError as exc:
            raise HTTPException(503, "SPICE data could not be loaded or does not cover this mission.") from exc
    sun, earth = visibility
    metrics = dict(sunlightPercent=round(float(sun.mean()*100), 2),
                   earthVisibilityPercent=round(float(earth.mean()*100), 2))
    if not instant:
        metrics.update(maxDarknessHours=longest_outage(sun, step/3600),
                       maxCommunicationBlackoutHours=longest_outage(earth, step/3600))
    terrain_source = ("LOLA 240 m polar DEM" if request.site.latitude <= -80 else "NASA Moon Trek global LOLA DEM (~400 m regional terrain)")
    message = (f"{terrain_source} horizon, 0.5-degree azimuth sectors, NASA DE440s / IAU_MOON. Surface observer; body-center visibility; finite disks and scattered light excluded. "
               + ("Single instant at 00:00 UTC; outage durations are unavailable." if instant else
                  "10-minute samples over the selected mission, starting at 00:00 UTC; outage durations are approximate and limited to this window."))
    return dict(status="computed", siteId=request.site.id, **metrics, message=message,
                timeline=dict(startUtc=request.date.isoformat() + "T00:00:00Z",
                              endUtc=end.isoformat() + "T00:00:00Z", sampleCount=count,
                              instant=instant, sun=visibility_segments(sun), earth=visibility_segments(earth)),
                customFilterResults=evaluate_custom_filters(request.customFilters, metrics))


@app.get("/api/horizon")
def horizon(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180)):
    try:
        observer, skyline = profile(latitude, longitude)
        return dict(observerM=observer.tolist(), horizonRadians=skyline.tolist())
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
