````md
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
````

If the output file is omitted:

```bash
python generate_svg.py input.json
```

The script automatically creates:

```bash
input.svg
```

---

# Example Input JSON

```json
{
  "request": "pfet",
  "dataset": {
    "pfet": {
      "gate rotation": "left",
      "design diode": "yes",
      "source kelvin": "yes",
      "source drain": "no",
      "replica": "source",
      "keepoutx": "170",
      "keepouty": "120",
      "user view": "yes",
      "design view": "yes",
      "instance": "M1",
      "resistance": "10",
      "Vds": "5",
      "device": "PFET",
      "width": "10u",
      "length": "1u",
      "array": "1"
    }
  }
}
```

---

# SVG Structure

Each generated SVG follows a predictable structure:

```xml
<svg>
  <g id="keepout">...</g>
  <g id="symbol">...</g>
  <g id="pins">...</g>
  <g id="labels">...</g>
</svg>
```

This makes the output easier to:

* Modify programmatically
* Style later
* Import into drawing systems
* Reuse in component libraries

---

# Supported Features

## Gate Rotation

Supported gate orientations:

* Left
* Right
* Top
* Bottom

---

## Optional Design Features

The generator supports:

* Design diode rendering
* Kelvin source markers
* Kelvin drain markers
* User-facing labels
* Internal design labels

---

# Output Goals

The SVG output is designed to be:

* Consistent
* Structured
* Editable
* Grid-aligned
* Easy to post-process later

This is intended for scalable electronic symbol library generation workflows.

---

# Example

```bash
python generate_svg.py pfet_request.json pfet_symbol.svg
```

Console output:

```bash
✓ pfet_symbol.svg [gate=left | user_view=yes | design_view=yes]
```

---

# Future Expansion

The current version focuses on PFET symbol generation.

The same architecture can later be extended for:

* NFET
* Resistors
* Capacitors
* Diodes
* Op-amps
* Custom schematic symbols

---

