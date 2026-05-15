#!/usr/bin/env python3
"""
Convert a PFET request JSON file into a schematic-style SVG symbol.
"""

from __future__ import annotations

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

UNIT = 10
PIN_PX = 30
# Tight spacing between channel bar and gate bar (gate dielectric), 1 grid unit
GATE_DIELECTRIC_PX = 10
MIN_W = 170
MIN_H = 120
C_SYMBOL = "#8B1A1A"
C_INSTANCE = "#9400D3"
C_LABEL = "#222222"
C_DESIGN = "#444444"
FONT = "monospace"
PIN_FILL = "#A0A0A0"


def c(v: float | int) -> int:
    """Round to integer pixel (text, non-wire)."""
    return int(round(float(v)))


def g10(x: float | int) -> int:
    """Nearest 10 px — all wire / schematic endpoints use this for grid compliance."""
    # Use half-up snapping (avoid Python's bankers-rounding surprises).
    v = float(x)
    return int(math.floor((v + 5.0) / 10.0) * 10)


# Half-pin offset on the 10 px grid (15 is not grid-aligned — use 10).
_INNER = 20


def _pin_contact_canvas_left(px: int, py: int, p: int = PIN_PX) -> tuple[int, int]:
    """Pin on canvas LEFT: wire at right-face centre → (px+30, py+10)."""
    return (px + p, py + _INNER)


def _pin_contact_canvas_right(px: int, py: int, p: int = PIN_PX) -> tuple[int, int]:
    """Pin on canvas RIGHT: wire at left-face centre → (px, py+10)."""
    return (px, py + _INNER)


def _pin_contact_canvas_top_row(px: int, py: int, p: int = PIN_PX) -> tuple[int, int]:
    """Pin on canvas TOP row (py=0): inward is down → bottom-face centre → (px+10, py+30)."""
    return (px + _INNER, py + p)


def _pin_contact_canvas_bottom_row(px: int, py: int, p: int = PIN_PX) -> tuple[int, int]:
    """Pin on canvas BOTTOM row (py=H−P): inward is up → top-face centre → (px+10, py)."""
    return (px + _INNER, py)


def pin_rect_layout(gate_rot: str, W: int, H: int, p: int = PIN_PX) -> dict[str, tuple[int, int]]:
    """
    Top-left (px, py) of each 30×30 pin — must match draw_pins exactly (single source of truth).
    """
    gy = gate_pin_y_snapped(H, p)
    gx = gate_pin_x_snapped_top_bottom(W, p)
    if gate_rot == "left":
        return {"source": (W - p, 0), "drain": (W - p, H - p), "gate": (0, gy)}
    if gate_rot == "right":
        return {"source": (0, 0), "drain": (0, H - p), "gate": (W - p, gy)}
    if gate_rot == "top":
        return {"source": (0, H - p), "drain": (W - p, H - p), "gate": (gx, 0)}
    if gate_rot == "bottom":
        return {"source": (0, 0), "drain": (W - p, 0), "gate": (gx, H - p)}
    raise ValueError(f"Unknown gate rotation: {gate_rot!r}")


def pin_wire_connect_points(gate_rot: str, W: int, H: int, p: int = PIN_PX) -> dict[str, tuple[int, int]]:
    """Inner-edge-centre wire anchors from pin_rect_layout + canvas-edge rules; snap with g10."""
    lay = pin_rect_layout(gate_rot, W, H, p)
    if gate_rot == "left":
        sprx, spry = lay["source"]
        dprx, dpry = lay["drain"]
        gprx, gpry = lay["gate"]
        src = _pin_contact_canvas_right(sprx, spry, p)
        drn = _pin_contact_canvas_right(dprx, dpry, p)
        gat = _pin_contact_canvas_left(gprx, gpry, p)
    elif gate_rot == "right":
        sprx, spry = lay["source"]
        dprx, dpry = lay["drain"]
        gprx, gpry = lay["gate"]
        src = _pin_contact_canvas_left(sprx, spry, p)
        drn = _pin_contact_canvas_left(dprx, dpry, p)
        gat = _pin_contact_canvas_right(gprx, gpry, p)
    elif gate_rot == "top":
        sprx, spry = lay["source"]
        dprx, dpry = lay["drain"]
        gprx, gpry = lay["gate"]
        src = _pin_contact_canvas_bottom_row(sprx, spry, p)
        drn = _pin_contact_canvas_bottom_row(dprx, dpry, p)
        gat = _pin_contact_canvas_top_row(gprx, gpry, p)
    elif gate_rot == "bottom":
        sprx, spry = lay["source"]
        dprx, dpry = lay["drain"]
        gprx, gpry = lay["gate"]
        src = _pin_contact_canvas_top_row(sprx, spry, p)
        drn = _pin_contact_canvas_top_row(dprx, dpry, p)
        gat = _pin_contact_canvas_bottom_row(gprx, gpry, p)
    else:
        raise ValueError(f"Unknown gate rotation: {gate_rot!r}")
    return {
        "source": (g10(src[0]), g10(src[1])),
        "drain": (g10(drn[0]), g10(drn[1])),
        "gate": (g10(gat[0]), g10(gat[1])),
    }


def gate_pin_y_snapped(H: int, P: int = PIN_PX) -> int:
    """Fix 1 — gate pin y for left/right rotations (integer canvas halving)."""
    return int(round((H // 2 - P // 2) / 10.0)) * 10


def gate_pin_x_snapped_top_bottom(W: int, P: int = PIN_PX) -> int:
    """Fix 3 — gate pin x for top/bottom (float centre before snap)."""
    return int(round((W / 2 - P / 2) / 10.0)) * 10


def snap_kelvin_rect_xywh(x: float, y: float, w: float, h: float) -> tuple[int, int, int, int]:
    """Fix 2 — Kelvin marker: x, y, width, height each a multiple of 10."""
    rx = int(round(x / 10.0)) * 10
    ry = int(round(y / 10.0)) * 10
    rw = int(round(w / 10.0)) * 10
    rh = int(round(h / 10.0)) * 10
    if rw < 10:
        rw = 10
    if rh < 10:
        rh = 10
    return rx, ry, rw, rh


def add_kelvin_rect(symbol_g: ET.Element, x: float, y: float, w: float, h: float) -> None:
    rx, ry, rw, rh = snap_kelvin_rect_xywh(x, y, w, h)
    add_rect_fill(symbol_g, rx, ry, rw, rh, PIN_FILL, grid=False)


def load_pfet(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if data.get("request") != "pfet":
        raise ValueError(f"Expected request 'pfet', got {data.get('request')!r}")
    params = data["dataset"]["pfet"]
    return {"data": data, "params": params}


def parse_params(params: dict[str, str]) -> dict[str, Any]:
    replica = params["replica"]
    if replica in ("source", "sorce"):
        replica = "source"

    keepout_x = int(params["keepoutx"])
    keepout_y = int(params["keepouty"])
    canvas_w = max(MIN_W, round(keepout_x / 10) * 10)
    canvas_h = max(MIN_H, round(keepout_y / 10) * 10)
    array = params["array"]
    show_array = array != "1"

    return {
        "gate_rot": params["gate rotation"],
        "design_diode": params["design diode"] == "yes",
        "src_kelvin": params["source kelvin"] == "yes",
        "src_drain": params["source drain"] == "yes",
        "replica": replica,
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "user_view": params["user view"] == "yes",
        "design_view": params["design view"] == "yes",
        "instance_txt": params["instance"],
        "resistance": params["resistance"],
        "vds": params["Vds"],
        "device": params["device"],
        "width": params["width"],
        "length": params["length"],
        "array": array,
        "show_array": show_array,
    }


def add_line(
    parent: ET.Element,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    color: str = C_SYMBOL,
    grid: bool = True,
) -> None:
    coord = g10 if grid else c
    el = ET.SubElement(parent, "line")
    el.set("x1", str(coord(x1)))
    el.set("y1", str(coord(y1)))
    el.set("x2", str(coord(x2)))
    el.set("y2", str(coord(y2)))
    el.set("stroke", color)
    el.set("stroke-width", str(width))
    el.set("stroke-linecap", "square")
    el.set("fill", "none")


def add_polyline(
    parent: ET.Element,
    points: list[tuple[float, float]],
    stroke_w: int,
    color: str = C_SYMBOL,
    grid: bool = True,
) -> None:
    coord = g10 if grid else c
    pts = " ".join(f"{coord(x)},{coord(y)}" for x, y in points)
    el = ET.SubElement(parent, "polyline")
    el.set("points", pts)
    el.set("stroke", color)
    el.set("stroke-width", str(stroke_w))
    el.set("stroke-linecap", "square")
    el.set("fill", "none")


def add_polygon(
    parent: ET.Element,
    points: list[tuple[float, float]],
    fill: str,
    grid: bool = True,
) -> None:
    coord = g10 if grid else c
    pts = " ".join(f"{coord(x)},{coord(y)}" for x, y in points)
    el = ET.SubElement(parent, "polygon")
    el.set("points", pts)
    el.set("fill", fill)
    el.set("stroke", "none")


def add_rect_fill(
    parent: ET.Element,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    grid: bool = True,
) -> None:
    coord = g10 if grid else c
    el = ET.SubElement(parent, "rect")
    el.set("x", str(coord(x)))
    el.set("y", str(coord(y)))
    el.set("width", str(max(1, coord(w))))
    el.set("height", str(max(1, coord(h))))
    el.set("fill", fill)


def draw_pins(
    pins_g: ET.Element,
    gate_rot: str,
    W: int,
    H: int,
    P: int,
) -> None:
    layout = pin_rect_layout(gate_rot, W, H, P)
    for key in ("source", "drain", "gate"):
        x, y = layout[key]
        r = ET.SubElement(pins_g, "rect")
        r.set("x", str(c(x)))
        r.set("y", str(c(y)))
        r.set("width", str(P))
        r.set("height", str(P))
        r.set("fill", PIN_FILL)
        r.set("stroke", "none")


def _lr_geometry(W: int, H: int, P: int) -> tuple[int, int, int, int, int, int]:
    """Left layout: inner_sd_x, channel_x, gate_bar_x, mid_y, y_top, y_bot."""
    inner_sd = W - P
    inner_gate = P
    usable = max(10, inner_sd - inner_gate)
    ch_off = max(40, g10(usable * 0.45))
    channel_x = inner_sd - ch_off
    gate_gap = GATE_DIELECTRIC_PX
    gate_bar_x = channel_x - gate_gap
    if gate_bar_x <= inner_gate:
        gate_bar_x = inner_gate + 10
        channel_x = gate_bar_x + gate_gap
    if channel_x >= inner_sd - 10:
        channel_x = inner_sd - 10
        gate_bar_x = max(inner_gate + 10, channel_x - gate_gap)
    mid_y = g10(H / 2)
    y_top = 10
    y_bot = H - 10
    return inner_sd, channel_x, gate_bar_x, mid_y, y_top, y_bot


def _tb_geometry_top(W: int, H: int, P: int) -> tuple[int, int, int, int, int, int]:
    """Top gate: inner_row_y (H-P), channel_y, gate_bar_y, mid_x, bend_s, bend_d."""
    inner_row = H - P
    usable_v = max(10, H - 2 * P)
    ch_off = max(40, g10(usable_v * 0.45))
    channel_y = inner_row - ch_off
    gate_gap = GATE_DIELECTRIC_PX
    gate_bar_y = channel_y - gate_gap
    if gate_bar_y <= P:
        gate_bar_y = P + 10
        channel_y = gate_bar_y + gate_gap
    if channel_y >= inner_row - 10:
        channel_y = inner_row - 10
        gate_bar_y = max(P + 10, channel_y - gate_gap)
    mid_x = g10(W / 2)
    usable_h = max(10, W - 2 * P)
    bend = max(40, g10(usable_h * 0.25))
    bend_s = P + bend
    bend_d = (W - P) - bend
    return inner_row, channel_y, gate_bar_y, mid_x, bend_s, bend_d


def _tb_geometry_bottom(W: int, H: int, P: int) -> tuple[int, int, int, int, int, int]:
    """Bottom gate: inner_row_y (P), channel_y, gate_bar_y, mid_x, bend_s, bend_d."""
    inner_row = P
    usable_v = max(10, H - 2 * P)
    ch_off = max(40, g10(usable_v * 0.45))
    channel_y = inner_row + ch_off
    gate_gap = GATE_DIELECTRIC_PX
    gate_bar_y = channel_y + gate_gap
    if gate_bar_y >= H - P:
        gate_bar_y = H - P - 10
        channel_y = gate_bar_y - gate_gap
    if channel_y <= inner_row + 10:
        channel_y = inner_row + 10
        gate_bar_y = min(H - P - 10, channel_y + gate_gap)
    mid_x = g10(W / 2)
    usable_h = max(10, W - 2 * P)
    bend = max(40, g10(usable_h * 0.25))
    bend_s = P + bend
    bend_d = (W - P) - bend
    return inner_row, channel_y, gate_bar_y, mid_x, bend_s, bend_d


def draw_symbol_left(symbol_g: ET.Element, W: int, H: int, P: int, design_diode: bool) -> None:
    inner_sd, channel_x, gate_bar_x, mid_y, y_top, y_bot = _lr_geometry(W, H, P)
    mv = max(10, g10(H * 0.05))
    conn = pin_wire_connect_points("left", W, H, P)
    sx, sy = conn["source"]
    dx, dy = conn["drain"]
    gx, gy = conn["gate"]

    tick = 40  # short stub off channel bar
    # long wires from pins to tick end
    add_line(symbol_g, sx, sy, channel_x + tick, sy, 2)
    add_line(symbol_g, dx, dy, channel_x + tick, dy, 2)
    # short ticks off channel bar
    add_line(symbol_g, channel_x, sy, channel_x + tick, sy, 2)
    add_line(symbol_g, channel_x, dy, channel_x + tick, dy, 2)
    # channel bar
    add_line(symbol_g, channel_x, sy, channel_x, dy, 3)
    add_line(symbol_g, gate_bar_x, mv, gate_bar_x, H - mv, 2)
    add_line(symbol_g, gx, gy, gate_bar_x, gy, 2)

    if design_diode:
        add_line(symbol_g, channel_x, sy, channel_x, dy, 1)
        add_polygon(
            symbol_g,
            [
                (gate_bar_x, gy - 8),
                (gate_bar_x, gy + 8),
                (channel_x, gy),
            ],
            C_SYMBOL,
        )

    # Arrow at channel bar tick junction
    ax = min(channel_x + tick, g10(sx) - 20)
    add_polygon(
        symbol_g,
        [(ax, sy - 8), (ax, sy + 8), (ax + 16, sy)],
        C_SYMBOL,
    )


def draw_symbol_right(symbol_g: ET.Element, W: int, H: int, P: int, design_diode: bool) -> None:
    inner_sd, channel_x, gate_bar_x, mid_y, y_top, y_bot = _lr_geometry(W, H, P)
    channel_x_r = W - channel_x
    gate_bar_x_r = W - gate_bar_x
    mv = max(10, g10(H * 0.05))
    conn = pin_wire_connect_points("right", W, H, P)
    sx, sy = conn["source"]
    dx, dy = conn["drain"]
    gx, gy = conn["gate"]

    tick = 40  # short stub off channel bar (leftward from channel)
    add_line(symbol_g, sx, sy, channel_x_r - tick, sy, 2)
    add_line(symbol_g, dx, dy, channel_x_r - tick, dy, 2)
    add_line(symbol_g, channel_x_r, sy, channel_x_r - tick, sy, 2)
    add_line(symbol_g, channel_x_r, dy, channel_x_r - tick, dy, 2)
    add_line(symbol_g, channel_x_r, sy, channel_x_r, dy, 3)
    add_line(symbol_g, gate_bar_x_r, mv, gate_bar_x_r, H - mv, 2)
    add_line(symbol_g, gx, gy, gate_bar_x_r, gy, 2)

    if design_diode:
        mx, my = channel_x_r, g10((sy + dy) / 2)
        add_line(symbol_g, mx, sy, mx, dy, 1)
        add_polygon(symbol_g, [(mx + 10, my - 10), (mx + 10, my + 10), (mx, my)], C_SYMBOL)

    ax = channel_x_r - tick
    add_polygon(
        symbol_g,
        [(ax, sy - 8), (ax, sy + 8), (ax - 16, sy)],
        C_SYMBOL,
    )


def draw_symbol_top(symbol_g: ET.Element, W: int, H: int, P: int, design_diode: bool) -> None:
    inner_row, channel_y, gate_bar_y, _, bend_s, bend_d = _tb_geometry_top(W, H, P)
    g1 = max(P, g10(W * 0.12))
    g2 = W - g1
    conn = pin_wire_connect_points("top", W, H, P)
    sx, sy = conn["source"]
    dx, dy = conn["drain"]
    gx, gy = conn["gate"]

    tick = 40  # short stub downward from horizontal channel bar (+y)
    add_polyline(
        symbol_g,
        [(sx, sy), (bend_s, sy), (bend_s, channel_y + tick)],
        2,
    )
    add_polyline(
        symbol_g,
        [(dx, dy), (bend_d, dy), (bend_d, channel_y + tick)],
        2,
    )
    add_line(symbol_g, bend_s, channel_y, bend_s, channel_y + tick, 2)
    add_line(symbol_g, bend_d, channel_y, bend_d, channel_y + tick, 2)
    add_line(symbol_g, P, channel_y, W - P, channel_y, 3)
    add_line(symbol_g, g1, gate_bar_y, g2, gate_bar_y, 2)
    add_line(symbol_g, gx, gy, gx, gate_bar_y, 2)

    if design_diode:
        diode_y = g10(sy + (channel_y - tick - sy) * 0.6)
        add_polygon(
            symbol_g,
            [
                (bend_s - 8, diode_y - 16),
                (bend_s + 8, diode_y - 16),
                (bend_s, diode_y),
            ],
            C_SYMBOL,
        )

    ay = channel_y + tick
    add_polygon(
        symbol_g,
        [(bend_s - 8, ay), (bend_s + 8, ay), (bend_s, ay - 16)],
        C_SYMBOL,
    )


def draw_symbol_bottom(symbol_g: ET.Element, W: int, H: int, P: int, design_diode: bool) -> None:
    inner_row, channel_y, gate_bar_y, _, bend_s, bend_d = _tb_geometry_bottom(W, H, P)
    g1 = max(P, g10(W * 0.12))
    g2 = W - g1
    conn = pin_wire_connect_points("bottom", W, H, P)
    sx, sy = conn["source"]
    dx, dy = conn["drain"]
    gx, gy = conn["gate"]

    tick = 40  # short stub upward from horizontal channel bar (-y)
    add_polyline(symbol_g, [(sx, sy), (bend_s, sy), (bend_s, channel_y - tick)], 2)
    add_polyline(symbol_g, [(dx, dy), (bend_d, dy), (bend_d, channel_y - tick)], 2)
    add_line(symbol_g, bend_s, channel_y, bend_s, channel_y - tick, 2)
    add_line(symbol_g, bend_d, channel_y, bend_d, channel_y - tick, 2)
    add_line(symbol_g, P, channel_y, W - P, channel_y, 3)
    add_line(symbol_g, g1, gate_bar_y, g2, gate_bar_y, 2)
    add_line(symbol_g, gx, gy, gx, gate_bar_y, 2)

    if design_diode:
        mx, my = g10((sx + dx) / 2), channel_y
        add_polygon(symbol_g, [(mx - 10, my - 10), (mx + 10, my - 10), (mx, my)], C_SYMBOL)

    ay = channel_y - tick
    add_polygon(
        symbol_g,
        [(bend_s - 8, ay), (bend_s + 8, ay), (bend_s, ay - 16)],
        C_SYMBOL,
    )


def kelvin_stub_left_source(symbol_g: ET.Element, W: int, H: int, P: int) -> None:
    _, channel_x, _, _, _, _ = _lr_geometry(W, H, P)
    conn = pin_wire_connect_points("left", W, H, P)
    sx, sy = conn["source"]
    mid_x = g10((sx + channel_x) / 2)
    kelvin_len = max(20, g10(H * 0.06))
    add_line(symbol_g, mid_x, sy, mid_x, sy + kelvin_len, 2)
    add_rect_fill(symbol_g, mid_x - 5, sy + kelvin_len - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_left_drain(symbol_g: ET.Element, W: int, H: int, P: int) -> None:
    _, channel_x, _, _, _, _ = _lr_geometry(W, H, P)
    conn = pin_wire_connect_points("left", W, H, P)
    dx, dy = conn["drain"]
    mid_x = g10((dx + channel_x) / 2)
    kelvin_len = max(20, g10(H * 0.06))
    add_line(symbol_g, mid_x, dy, mid_x, dy - kelvin_len, 2)
    add_rect_fill(symbol_g, mid_x - 5, dy - kelvin_len - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_right_source(symbol_g: ET.Element, W: int, H: int, P: int) -> None:
    _, channel_x, _, _, _, _ = _lr_geometry(W, H, P)
    channel_x_r = W - channel_x
    conn = pin_wire_connect_points("right", W, H, P)
    sx, sy = conn["source"]
    mid_x = g10((sx + channel_x_r) / 2)
    kelvin_len = max(20, g10(H * 0.06))
    add_line(symbol_g, mid_x, sy, mid_x, sy + kelvin_len, 2)
    add_rect_fill(symbol_g, mid_x - 5, sy + kelvin_len - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_right_drain(symbol_g: ET.Element, W: int, H: int, P: int) -> None:
    _, channel_x, _, _, _, _ = _lr_geometry(W, H, P)
    channel_x_r = W - channel_x
    conn = pin_wire_connect_points("right", W, H, P)
    dx, dy = conn["drain"]
    mid_x = g10((dx + channel_x_r) / 2)
    kelvin_len = max(20, g10(H * 0.06))
    add_line(symbol_g, mid_x, dy, mid_x, dy - kelvin_len, 2)
    add_rect_fill(symbol_g, mid_x - 5, dy - kelvin_len - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_top_source(symbol_g: ET.Element, W: int, H: int, P: int) -> None:
    _, channel_y, _, _, bend_s, _ = _tb_geometry_top(W, H, P)
    conn = pin_wire_connect_points("top", W, H, P)
    sx, sy = conn["source"]
    mid_x = g10((sx + bend_s) / 2)
    mid_y = sy
    kelvin_len = max(50, g10(W * 0.10))
    add_line(symbol_g, mid_x, mid_y, mid_x - kelvin_len, mid_y, 2)
    add_rect_fill(symbol_g, max(0, mid_x - kelvin_len - 5), mid_y - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_top_drain(symbol_g: ET.Element, W: int, H: int, P: int, Wtot: int) -> None:
    _, channel_y, _, _, _, bend_d = _tb_geometry_top(Wtot, H, P)
    conn = pin_wire_connect_points("top", Wtot, H, P)
    dx, dy = conn["drain"]
    mid_x = g10((dx + bend_d) / 2)
    mid_y = dy
    kelvin_len = max(50, g10(Wtot * 0.10))
    add_line(symbol_g, mid_x, mid_y, mid_x + kelvin_len, mid_y, 2)
    add_rect_fill(symbol_g, mid_x + kelvin_len - 5, mid_y - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_bottom_source(symbol_g: ET.Element, W: int, H: int, P: int) -> None:
    _, channel_y, _, _, bend_s, _ = _tb_geometry_bottom(W, H, P)
    conn = pin_wire_connect_points("bottom", W, H, P)
    sx, sy = conn["source"]
    mid_x = g10((sx + bend_s) / 2)
    mid_y = sy
    kelvin_len = max(50, g10(W * 0.10))
    add_line(symbol_g, mid_x, mid_y, mid_x - kelvin_len, mid_y, 2)
    add_rect_fill(symbol_g, mid_x - kelvin_len - 5, mid_y - 5, 10, 10, PIN_FILL, grid=False)


def kelvin_stub_bottom_drain(symbol_g: ET.Element, W: int, H: int, P: int, Wtot: int) -> None:
    _, channel_y, _, _, _, bend_d = _tb_geometry_bottom(Wtot, H, P)
    conn = pin_wire_connect_points("bottom", Wtot, H, P)
    dx, dy = conn["drain"]
    mid_x = g10((dx + bend_d) / 2)
    mid_y = dy
    kelvin_len = max(50, g10(Wtot * 0.10))
    add_line(symbol_g, mid_x, mid_y, mid_x + kelvin_len, mid_y, 2)
    add_rect_fill(symbol_g, mid_x + kelvin_len - 5, mid_y - 5, 10, 10, PIN_FILL, grid=False)


def draw_symbol(
    symbol_g: ET.Element,
    gate_rot: str,
    W: int,
    H: int,
    P: int,
    design_diode: bool,
    src_kelvin: bool,
    src_drain: bool,
) -> None:
    if gate_rot == "left":
        draw_symbol_left(symbol_g, W, H, P, design_diode)
        if src_kelvin:
            kelvin_stub_left_source(symbol_g, W, H, P)
        if src_drain:
            kelvin_stub_left_drain(symbol_g, W, H, P)
    elif gate_rot == "right":
        draw_symbol_right(symbol_g, W, H, P, design_diode)
        if src_kelvin:
            kelvin_stub_right_source(symbol_g, W, H, P)
        if src_drain:
            kelvin_stub_right_drain(symbol_g, W, H, P)
    elif gate_rot == "top":
        draw_symbol_top(symbol_g, W, H, P, design_diode)
        if src_kelvin:
            kelvin_stub_top_source(symbol_g, W, H, P)
        if src_drain:
            kelvin_stub_top_drain(symbol_g, W, H, P, W)
    elif gate_rot == "bottom":
        draw_symbol_bottom(symbol_g, W, H, P, design_diode)
        if src_kelvin:
            kelvin_stub_bottom_source(symbol_g, W, H, P)
        if src_drain:
            kelvin_stub_bottom_drain(symbol_g, W, H, P, W)
    else:
        raise ValueError(f"Unknown gate rotation: {gate_rot!r}")


def add_text(
    parent: ET.Element,
    x: float,
    y: float,
    text: str,
    size: int,
    fill: str,
    anchor: str = "start",
    weight: str = "normal",
) -> None:
    t = ET.SubElement(parent, "text")
    t.set("x", str(c(x)))
    t.set("y", str(c(y)))
    t.set("font-family", FONT)
    t.set("font-size", str(size))
    t.set("fill", fill)
    t.set("text-anchor", anchor)
    if weight == "bold":
        t.set("font-weight", "bold")
    t.text = text


def add_text_tspan_stack(
    parent: ET.Element,
    x: float,
    y: float,
    lines: list[tuple[str, int, str, str]],
    anchor: str = "start",
    dy: int = 14,
) -> None:
    """Multiple lines in one <text> using <tspan dy=...> (e.g. top-gate label spacing)."""
    t = ET.SubElement(parent, "text")
    t.set("x", str(c(x)))
    t.set("y", str(c(y)))
    t.set("font-family", FONT)
    t.set("text-anchor", anchor)
    first = True
    for text, size, fill, weight in lines:
        span = ET.SubElement(t, "tspan")
        if not first:
            span.set("x", str(c(x)))
            span.set("dy", str(dy))
        first = False
        span.set("font-size", str(size))
        span.set("fill", fill)
        if weight == "bold":
            span.set("font-weight", "bold")
        span.text = text


def draw_labels(
    labels_g: ET.Element,
    gate_rot: str,
    W: int,
    H: int,
    user_view: bool,
    design_view: bool,
    instance_txt: str,
    vds: str,
    resistance: str,
    device: str,
    width: str,
    length: str,
    array: str,
    show_array: bool,
) -> None:
    if not user_view and not design_view:
        return
    # Suppress labels on extreme aspect ratio canvases
    if W > H * 1.5:   # very flat (e.g. 25e9b05f)
        return
    if H > W * 3:     # very tall/narrow (e.g. 28e63f88)
        return

    pad = 10

    # Safe label placement: use quadrant opposite symbol density.
    # left  -> labels on left side (top-left + bottom-left)
    # right -> labels on right side (top-right + bottom-right)
    # top   -> labels on top band
    # bottom-> labels on bottom band
    if gate_rot == "left":
        inst_x, inst_anchor, inst_y = pad, "start", 18
        uv_x, uv_anchor, vds_y, res_y = pad, "start", 40, 55
        d_x, d_anchor = pad, "start"
        y_d, y_w, y_l, y_a = H - 6, H - 18, H - 30, H - 42
    elif gate_rot == "right":
        inst_x, inst_anchor, inst_y = W - pad, "end", 18
        uv_x, uv_anchor, vds_y, res_y = W - pad, "end", 40, 55
        d_x, d_anchor = W - pad, "end"
        y_d, y_w, y_l, y_a = H - 6, H - 18, H - 30, H - 42
    elif gate_rot == "top":
        inst_x, inst_anchor, inst_y = W - pad, "end", H - PIN_PX - 14
        stack_start_y = max(PIN_PX + 10, H - PIN_PX - 14 - 84)
    elif gate_rot == "bottom":
        inst_x, inst_anchor, inst_y = W - pad, "end", PIN_PX + 18
        uv_x, uv_anchor, vds_y, res_y = pad, "start", PIN_PX + 18, PIN_PX + 32
        d_x, d_anchor = pad, "start"
        y_d, y_w, y_l, y_a = PIN_PX + 48, PIN_PX + 62, PIN_PX + 76, PIN_PX + 90
    else:
        inst_x, inst_anchor, inst_y = W - pad, "end", 18
        uv_x, uv_anchor, vds_y, res_y = pad, "start", 40, 55
        d_x, d_anchor = pad, "start"
        y_d, y_w, y_l, y_a = H - 6, H - 18, H - 30, H - 42

    if gate_rot == "top":
        if user_view:
            add_text(labels_g, inst_x, inst_y, instance_txt, 12, C_INSTANCE, inst_anchor, "bold")
        stack_lines_top: list[tuple[str, int, str, str]] = []
        if user_view:
            stack_lines_top.append((f"{vds}V", 10, C_LABEL, "normal"))
            stack_lines_top.append((f"{resistance} Ω", 10, C_LABEL, "normal"))
        if design_view:
            stack_lines_top.append((device, 9, C_DESIGN, "normal"))
            stack_lines_top.append((f"W={width}", 9, C_DESIGN, "normal"))
            stack_lines_top.append((f"L={length}", 9, C_DESIGN, "normal"))
            if show_array:
                stack_lines_top.append((f"array={array}", 9, C_DESIGN, "normal"))
        if stack_lines_top:
            add_text_tspan_stack(labels_g, pad, stack_start_y, stack_lines_top, "start", 14)
    else:
        if user_view:
            add_text(labels_g, inst_x, inst_y, instance_txt, 12, C_INSTANCE, inst_anchor, "bold")
            add_text(labels_g, uv_x, vds_y, f"{vds}V", 10, C_LABEL, uv_anchor, "normal")
            add_text(labels_g, uv_x, res_y, f"{resistance} Ω", 10, C_LABEL, uv_anchor, "normal")

        if design_view:
            add_text(labels_g, d_x, y_d, device, 9, C_DESIGN, d_anchor, "normal")
            add_text(labels_g, d_x, y_w, f"W={width}", 9, C_DESIGN, d_anchor, "normal")
            add_text(labels_g, d_x, y_l, f"L={length}", 9, C_DESIGN, d_anchor, "normal")
            if show_array:
                add_text(labels_g, d_x, y_a, f"array={array}", 9, C_DESIGN, d_anchor, "normal")


def build_svg(params: dict[str, Any]) -> ET.ElementTree:
    W = params["canvas_w"]
    H = params["canvas_h"]
    P = PIN_PX
    gate_rot = params["gate_rot"]

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(W),
            "height": str(H),
            "viewBox": f"0 0 {W} {H}",
        },
    )

    g_keep = ET.SubElement(svg, "g", {"id": "keepout"})
    r = ET.SubElement(g_keep, "rect")
    r.set("x", "0")
    r.set("y", "0")
    r.set("width", str(W))
    r.set("height", str(H))
    r.set("fill", "none")
    r.set("stroke", "#404040")
    r.set("stroke-width", "1")
    r.set("stroke-dasharray", "5,3")

    g_sym = ET.SubElement(svg, "g", {"id": "symbol"})
    draw_symbol(
        g_sym,
        gate_rot,
        W,
        H,
        P,
        params["design_diode"],
        params["src_kelvin"],
        params["src_drain"],
    )

    g_pins = ET.SubElement(svg, "g", {"id": "pins"})
    draw_pins(g_pins, gate_rot, W, H, P)

    g_lab = ET.SubElement(svg, "g", {"id": "labels"})
    draw_labels(
        g_lab,
        gate_rot,
        W,
        H,
        params["user_view"],
        params["design_view"],
        params["instance_txt"],
        params["vds"],
        params["resistance"],
        params["device"],
        params["width"],
        params["length"],
        params["array"],
        params["show_array"],
    )

    return ET.ElementTree(svg)


def write_svg(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    if len(argv) < 2:
        print("Usage: python generate_svg.py <input.json> [output.svg]", file=sys.stderr)
        return 1

    in_path = Path(argv[1])
    if not in_path.is_file():
        print(f"Not found: {in_path}", file=sys.stderr)
        return 1

    if len(argv) >= 3:
        out_path = Path(argv[2])
    else:
        out_path = in_path.with_suffix(".svg")

    loaded = load_pfet(in_path)
    params = parse_params(loaded["params"])
    tree = build_svg(params)
    write_svg(tree, out_path)

    uv = "yes" if params["user_view"] else "no"
    dv = "yes" if params["design_view"] else "no"
    print(f"✓ {out_path.name} [gate={params['gate_rot']} | user_view={uv} | design_view={dv}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
