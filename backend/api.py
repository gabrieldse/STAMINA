"""Local SPICE-based, geometric horizon analysis API."""
from datetime import date, timedelta, datetime, timezone
from datetime import date as CalendarDate
from threading import Lock

import numpy as np
import spiceypy as sp
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from SMEData.kernel_loaders import load_kernels
from backend.custom_filter_engine import CustomFilterRule, evaluate_custom_filters

app = FastAPI()
SPICE_LOCK = Lock()


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
    sunElevation: float = Field(default=0, ge=-10, le=30, allow_inf_nan=False)
    earthElevation: float = Field(default=0, ge=-10, le=30, allow_inf_nan=False)
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
            lon, lat = np.radians([request.site.longitude, request.site.latitude])
            up = np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
            site = 1737.4 * up
            visibility = []
            for body, threshold in [("SUN", request.filters.sunElevation), ("EARTH", request.filters.earthElevation)]:
                positions, _ = sp.spkpos(body, times, "IAU_MOON", "NONE", "MOON")
                vectors = np.asarray(positions).reshape(-1, 3) - site
                elevation = np.degrees(np.arcsin(np.clip((vectors @ up) / np.linalg.norm(vectors, axis=1), -1, 1)))
                visibility.append(elevation > threshold)
        except sp.utils.exceptions.SpiceyError as exc:
            raise HTTPException(503, "SPICE data could not be loaded or does not cover this mission.") from exc
    sun, earth = visibility
    metrics = dict(sunlightPercent=round(float(sun.mean()*100), 2),
                   earthVisibilityPercent=round(float(earth.mean()*100), 2))
    if not instant:
        metrics.update(maxDarknessHours=longest_outage(sun, step/3600),
                       maxCommunicationBlackoutHours=longest_outage(earth, step/3600))
    message = ("Geometric horizon estimate using NASA DE440s and IAU_MOON; terrain shadows and obstructions are not included. "
               + ("Single instant at 00:00 UTC; outage durations are unavailable." if instant else
                  "10-minute samples over the selected mission, starting at 00:00 UTC; outage durations are approximate and limited to this window."))
    return dict(status="computed", siteId=request.site.id, **metrics, message=message,
                timeline=dict(startUtc=request.date.isoformat() + "T00:00:00Z",
                              endUtc=end.isoformat() + "T00:00:00Z", sampleCount=count,
                              instant=instant, sun=visibility_segments(sun), earth=visibility_segments(earth)),
                customFilterResults=evaluate_custom_filters(request.customFilters, metrics))
