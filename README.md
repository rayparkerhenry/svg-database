# PFET SVG Symbol Generator

This Python script generates schematic-style SVG symbols for PFET electronic components from a structured JSON request file.

The goal is to create consistent, editable SVG files that can be used as part of an electronic component symbol library. Each generated SVG follows a predictable structure, making it easier to modify, style, or place into a final drawing system later.

## Features

- Generates PFET symbols in SVG format
- Supports gate rotation: `left`, `right`, `top`, and `bottom`
- Keeps schematic wires aligned to a 10px grid
- Adds separate SVG groups for:
  - `keepout`
  - `symbol`
  - `pins`
  - `labels`
- Supports optional design diode
- Supports source Kelvin and source/drain Kelvin markers
- Supports user-facing and design-facing labels
- Automatically sizes the canvas based on keepout values

## Requirements

- Python 3.10 or newer
- No external Python packages required

## Usage

```bash
python generate_svg.py input.json output.svg
