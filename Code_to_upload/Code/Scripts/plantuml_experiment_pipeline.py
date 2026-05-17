#!/usr/bin/env python3
"""
Compatibility entrypoint for the modular PlantUML experiment pipeline.

The implementation now lives in the `plantuml_pipeline` package.
"""

from __future__ import annotations

from plantuml_pipeline.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
