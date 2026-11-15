"""Run with .venv/Scripts/python.exe -m backend.benchmark_visibility."""
import json
import platform
from datetime import date
from statistics import median
from time import perf_counter

import numba

from backend.api import positions
from backend.visibility_map import observers, terrain, trace, trace_optimized, visibility_map, body_map


def timed(call):
    start = perf_counter()
    result = call()
    return result, perf_counter()-start


def main():
    vectors = positions(date(2026, 11, 15))
    terrain()
    points = observers(256)[1]
    _, first = timed(lambda: trace_optimized(points, vectors['sun']))
    report = dict(python=platform.python_version(), numba=numba.__version__,
                  threads=numba.get_num_threads(), firstCompiledCallSeconds=round(first, 4), measurements=[])
    for size in [256, 384, 768, 1536, 2048]:
        points = observers(size)[1]
        row = dict(size=size, resolutionM=round(608011.216/size, 1))
        for body in ['sun', 'earth']:
            row[body+'Seconds'] = round(median(timed(lambda: trace_optimized(points, vectors[body]))[1] for _ in range(3)), 4)
            if size == 256:
                row[body+'NumpySeconds'] = round(median(timed(lambda: trace(points, vectors[body]))[1] for _ in range(3)), 4)
        body_map.cache_clear()
        visibility_map.cache_clear()
        payload, elapsed = timed(lambda: visibility_map(size, tuple(vectors['sun']), tuple(vectors['earth']), 'bitset'))
        row['combinedMapSeconds'] = round(elapsed, 4)
        encoded, elapsed = timed(lambda: json.dumps(payload))
        row['jsonSeconds'] = round(elapsed, 4)
        row['responseBytes'] = len(encoded.encode())
        report['measurements'].append(row)
        print(json.dumps(row), flush=True)
    from pathlib import Path
    Path('backend/visibility_benchmark.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
