# SVG Symbol Generator

This Python script generates schematic-style SVG symbols for PFET electronic components from a structured JSON request file.

The goal is to create consistent, editable SVG files that can be used as part of an electronic component symbol library. Each generated SVG follows a predictable structure, making it easier to modify, style, or place into a final drawing system later.

---

# Features

- Generates PFET symbols in SVG format
- Supports gate rotation:
  - `left`
  - `right`
  - `top`
  - `bottom`
- Keeps schematic wires aligned to a 10px grid
- Uses a consistent SVG structure for easier editing
- Supports:
  - Design diode
  - Source Kelvin marker
  - Source/Drain Kelvin marker
  - User labels
  - Design labels
- Automatically sizes the SVG canvas from keepout values
- No external Python dependencies required

---

# Requirements

- Python 3.10+

No external libraries are required.

---

# Usage

```bash
python generate_svg.py input.json output.svg
