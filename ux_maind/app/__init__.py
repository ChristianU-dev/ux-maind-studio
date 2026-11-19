"""Installable product; no research registry, publisher or checkout dependency."""

import os

# Native Docling Graph can import LiteLLM before the settings page is opened.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_TELEMETRY"] = "False"
__version__ = "0.5.6"
