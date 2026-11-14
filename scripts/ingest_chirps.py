"""Lluvia mensual CHIRPS v3 en el punto de la finca, sin bajar los mapas completos (tarea 4.8).

CHIRPS v3 publica un GeoTIFF mensual para Latinoamérica (~4 MB cada uno, ~2 GB para
1981–2026). Este script lee solo lo necesario de cada archivo con peticiones HTTP
por rango: la cabecera, el directorio TIFF y las dos filas que tocan el punto
(~25 KB por mes, ~15 MB en total). No requiere login.

El punto 10.55, −85.50 cae justo en la esquina de cuatro celdas de 0,05°, así que
el valor mensual es la media de esas 2×2 celdas (un cuadro de ~11 km × 11 km
centrado en el punto).

Las descargas usan ``curl.exe``/``curl`` porque valida el certificado con el
almacén del sistema operativo; nunca se desactiva la verificación TLS.

Uso:
    python -m scripts.ingest_chirps --start 1981-01 --end 2026-10

Escribe ``datasets/processed/climate/chirps_v3_monthly_10.55_-85.5.json`` y guarda
en ``datasets/raw/chirps/`` (ignorado por Git) el valor y los bytes leídos por mes,
para no repetir peticiones.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/tifs/chirps-v3.0.{year}.{month:02d}.tif"
SOURCE_REF = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/tifs/"
CITATION = ("Funk et al. (2015) The climate hazards infrared precipitation with stations, "
            "Sci. Data 2:150066; CHIRPS v3.0, Climate Hazards Center, UC Santa Barbara.")
LAT, LON = 10.55, -85.50
RAW_DIR = ROOT / "datasets" / "raw" / "chirps"
OUTPUT = ROOT / "datasets" / "processed" / "climate" / "chirps_v3_monthly_10.55_-85.5.json"
NODATA_LIMIT = -1.0  # CHIRPS usa -9999 como sin dato


def _curl() -> str:
    exe = shutil.which("curl.exe") or shutil.which("curl")
    if exe is None:
        raise RuntimeError("se necesita curl para las peticiones por rango")
    return exe


def fetch_range(url: str, start: int, end: int | None = None) -> bytes:
    spec = f"{start}-" if end is None else f"{start}-{end}"
    result = subprocess.run([_curl(), "-sfL", "--retry", "3", "-r", spec, url],
                            capture_output=True, check=True, timeout=120)
    if end is not None and len(result.stdout) != end - start + 1:
        raise ValueError(f"{url}: rango {spec} incompleto ({len(result.stdout)} bytes)")
    return result.stdout


def lzw_decode(data: bytes) -> bytes:
    """Decodificador LZW de TIFF (MSB primero, cambio de ancho anticipado)."""
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    out = bytearray()
    width, bitpos, nbits = 9, 0, len(data) * 8
    previous = None
    while bitpos + width <= nbits:
        byte, shift = divmod(bitpos, 8)
        chunk = int.from_bytes(data[byte:byte + 4].ljust(4, b"\0"), "big")
        code = (chunk >> (32 - shift - width)) & ((1 << width) - 1)
        bitpos += width
        if code == 256:  # clear
            table = table[:258]
            width, previous = 9, None
            continue
        if code == 257:  # fin de información
            break
        if previous is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(previous + entry[:1])
        elif code == len(table):
            entry = previous + previous[:1]
            table.append(entry)
        else:
            raise ValueError("código LZW inválido")
        out += entry
        previous = entry
        if len(table) + 1 >= (1 << width) and width < 12:
            width += 1
    return bytes(out)


TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 11: 4, 12: 8, 16: 8}
TYPE_FORMATS = {1: "B", 3: "H", 4: "I", 11: "f", 12: "d", 16: "Q"}


def parse_tail(tail: bytes, base: int) -> dict[int, tuple]:
    """Lee el primer IFD cuando está, con sus valores, en el bloque ``tail`` que empieza en ``base``."""
    count = struct.unpack("<H", tail[:2])[0]
    tags = {}
    for i in range(count):
        entry = tail[2 + 12 * i:14 + 12 * i]
        tag, typ, n = struct.unpack("<HHI", entry[:8])
        if typ not in TYPE_FORMATS:
            continue
        size = TYPE_SIZES[typ] * n
        if size <= 4:
            raw = entry[8:8 + size]
        else:
            pointer = struct.unpack("<I", entry[8:12])[0] - base
            if pointer < 0 or pointer + size > len(tail):
                continue  # tags fuera del bloque leído; las necesarias se validan abajo
            raw = tail[pointer:pointer + size]
        tags[tag] = struct.unpack("<" + TYPE_FORMATS[typ] * n, raw)
    return tags


def point_cells(tags: dict[int, tuple]) -> tuple[list[int], list[int]]:
    """Filas y columnas cuyos bordes tocan el punto (2×2 si cae en una esquina)."""
    scale_x, scale_y = tags[33550][:2]
    _, _, _, origin_x, origin_y, _ = tags[33922]
    col = (LON - origin_x) / scale_x
    row = (origin_y - LAT) / scale_y

    def around(value: float) -> list[int]:
        nearest = round(value)
        # La escala viene en float32 (0,0500000007), así que una esquina exacta queda a ~1e-5.
        return [nearest - 1, nearest] if abs(value - nearest) < 1e-3 else [int(value)]

    return around(row), around(col)


def read_month(year: int, month: int) -> dict:
    """Valor mensual (mm) en el punto, con detalle de celdas y bytes leídos."""
    url = BASE_URL.format(year=year, month=month)
    header = fetch_range(url, 0, 7)
    if header[:4] != b"II*\x00":
        raise ValueError(f"{url}: se esperaba TIFF little-endian clásico")
    ifd = struct.unpack("<I", header[4:8])[0]
    tail = fetch_range(url, ifd)
    tags = parse_tail(tail, ifd)
    width, height = tags[256][0], tags[257][0]
    required = {258: 32, 259: 5, 277: 1, 278: 1, 339: 3}
    for tag, expected in required.items():
        if tags.get(tag, (None,))[0] != expected:
            raise ValueError(f"{url}: tag {tag}={tags.get(tag)} no soportado (se esperaba {expected})")
    if tags.get(317, (1,))[0] != 1:
        raise ValueError(f"{url}: predictor TIFF no soportado")
    rows, cols = point_cells(tags)
    offsets, counts = tags[273], tags[279]
    if len(offsets) != height or len(counts) != height:
        raise ValueError(f"{url}: tabla de franjas incompleta")
    first, last = min(rows), max(rows)
    block = fetch_range(url, offsets[first], offsets[last] + counts[last] - 1)
    cells = []
    for row in rows:
        start = offsets[row] - offsets[first]
        pixels = lzw_decode(block[start:start + counts[row]])
        if len(pixels) != 4 * width:
            raise ValueError(f"{url}: fila {row} decodificada con {len(pixels)} bytes")
        for col in cols:
            value = struct.unpack("<f", pixels[4 * col:4 * col + 4])[0]
            cells.append({"row": row, "col": col, "mm": None if value <= NODATA_LIMIT else round(value, 3)})
    values = [c["mm"] for c in cells]
    mean = None if any(v is None for v in values) else round(sum(values) / len(values), 2)
    return {"month": f"{year}-{month:02d}", "precipitation_mm": mean, "cells": cells,
            "bytes_read": len(header) + len(tail) + len(block), "url": url}


def _cached(year: int, month: int, refresh: bool) -> dict:
    path = RAW_DIR / f"{year}-{month:02d}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    record = read_month(year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


def months_between(start: str, end: str) -> list[tuple[int, int]]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", default="1981-01")
    parser.add_argument("--end", default="2026-10")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    months = months_between(args.start, args.end)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda ym: _cached(*ym, args.refresh), months))
    document = {
        "_mock": False,
        "dataset": "CHIRPS v3.0 monthly (latam)",
        "zona": {"lat": LAT, "lon": LON},
        "units": {"precipitation_mm": "mm/month"},
        "method": "media de las 2x2 celdas de 0,05° cuyos bordes tocan el punto; lectura HTTP por rango",
        "generado": datetime.now(timezone.utc).isoformat(),
        "source_refs": [SOURCE_REF],
        "citation": CITATION,
        "months": [{"month": r["month"], "precipitation_mm": r["precipitation_mm"],
                    "cells_mm": [c["mm"] for c in r["cells"]]} for r in records],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(r["bytes_read"] for r in records)
    print(f"{len(records)} meses, {total / 1e6:.1f} MB leídos → {args.output}")


if __name__ == "__main__":
    main()
