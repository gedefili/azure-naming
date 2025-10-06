# File: utils/slug_fetcher.py
# Version: 1.1.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Fetches and parses slugs from the HCL 'defined_specs' file in Azure naming repo.

import logging
import re
from typing import Dict

import requests

# Constants
DEFINED_SPECS_URL = "https://raw.githubusercontent.com/Azure/terraform-azurerm-naming/master/docs/defined_specs"

_slug_pattern = re.compile(r"\s*(\w+)\s*=\s*\"([^\"]+)\"")


class SlugSourceError(RuntimeError):
    """Raised when slug definitions cannot be loaded from the upstream source."""

def get_all_remote_slugs() -> Dict[str, str]:
    """
    Fetches the Azure naming 'defined_specs' file and returns a slug-to-resource mapping.
    Returns:
        dict: {"slug": "resource_type_name"}
    """
    try:
        logging.info("Fetching defined_specs from Azure naming repo...")
        response = requests.get(DEFINED_SPECS_URL, timeout=10)
        response.raise_for_status()
        hcl_text = response.text

        slug_map: Dict[str, str] = {}

        # Extract the az = { ... } block (assumes it's the only block)
        block_start = hcl_text.find("az = {")
        block_end = hcl_text.find("}\n", block_start)
        if block_start == -1 or block_end == -1:
            raise ValueError("Could not find 'az = { ... }' block in defined_specs")

        block_content = hcl_text[block_start:block_end]

        for match in _slug_pattern.finditer(block_content):
            full_name, slug = match.groups()
            slug_map[slug] = full_name

        logging.info("Parsed %s slug mappings.", len(slug_map))
        return slug_map

    except Exception as exc:
        logging.exception("Failed to fetch or parse defined_specs file.")
        raise SlugSourceError("Unable to load slug definitions from GitHub") from exc
