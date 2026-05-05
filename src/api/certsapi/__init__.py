"""Public API surface for the certsapi package."""

from __future__ import annotations

import os

__version__: str = os.environ.get("BUILD_VERSION", "0.0.0+dev")
