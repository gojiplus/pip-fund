#!/usr/bin/env python3
"""
pypi-fund.py – Discover funding links for Python packages

This script is a more polished proof‑of‑concept for enumerating funding
information in Python packages.  It draws inspiration from npm's
`npm fund` command and improves upon a simple implementation by:

* Normalising metadata labels according to the Python packaging
  specifications (see PEP 753 and the "Well‑Known Project URLs" section
  of the core metadata spec:contentReference[oaicite:0]{index=0}).  Labels like
  "Funding", "Donate" or "Sponsor this project" are all collapsed into
  the same category via a normalisation function.
* Recognising common aliases for funding: ``funding``, ``sponsor``,
  ``donate`` and ``donation``, along with any label containing the
  word "fund" or "sponsor".  Additional aliases can be added to
  ``FUNDING_ALIASES`` below.
* Grouping multiple funding URLs per package so that each project is
  printed once with all its funding entries.
* **Grouping funding entries across packages** so that identical
  funding links (same label and URL) are displayed once along with
  the list of packages that declare them, reducing duplicate output.
* **Normalising URLs** by stripping query parameters and fragments
  (anything after ``?`` or ``#``) when comparing funding links, so
  links that differ only by tracking parameters are treated as the same.
* Providing optional JSON and Markdown output via ``--json`` and
  ``--markdown`` command‑line flags.  When neither flag is given, a
  human‑readable plain‑text report is produced.
* (Optional) Querying the PyPI JSON API for funding information when
  packages are not installed or to supplement local metadata.  Use
  ``--remote`` to enable this behaviour.  Note that network access is
  required and may fail when connectivity is unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from urllib.parse import urlparse, urlunparse
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

try:
    from importlib import metadata as importlib_metadata
except ImportError:
    import importlib_metadata  # type: ignore

try:
    import requests  # type: ignore
except ImportError:
    requests = None

FUNDING_ALIASES: set[str] = {
    "funding",
    "sponsor",
    "donate",
    "donation",
}

def normalise_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", label)
    return cleaned.lower()

def normalise_url(url: str) -> str:
    """Strip query parameters and fragments from a URL."""
    try:
        parsed = urlparse(url)
        cleaned = parsed._replace(query="", fragment="")
        return urlunparse(cleaned)
    except Exception:
        return url

def extract_funding_urls_from_dist(dist: importlib_metadata.Distribution) -> List[Tuple[str, str]]:
    funding_entries: List[Tuple[str, str]] = []
    try:
        project_urls = dist.metadata.get_all("Project-URL", []) or []
    except Exception:
        project_urls = []
    for url_entry in project_urls:
        if "," in url_entry:
            label, url = url_entry.split(",", 1)
            label = label.strip()
            url = url.strip()
            norm = normalise_label(label)
            if (norm in FUNDING_ALIASES or "fund" in norm or "sponsor" in norm):
                funding_entries.append((label, url))
        else:
            url = url_entry.strip()
            if re.search(r"fund|sponsor", url, re.IGNORECASE):
                funding_entries.append(("Generic Link", url))
    return funding_entries

def query_pypi_project_urls(package_name: str) -> Dict[str, str]:
    if requests is None:
        return {}
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            project_urls: Mapping[str, str] = data.get("info", {}).get("project_urls", {}) or {}
            return {str(k): str(v) for k, v in project_urls.items() if k and v}
    except Exception:
        pass
    return {}

def gather_funding_info(package_names: Iterable[str], use_remote: bool) -> Dict[str, List[Tuple[str, str]]]:
    results: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    if package_names:
        for pkg in package_names:
            try:
                dist = importlib_metadata.distribution(pkg)
                results[pkg].extend(extract_funding_urls_from_dist(dist))
            except importlib_metadata.PackageNotFoundError:
                if use_remote:
                    for lbl, url in query_pypi_project_urls(pkg).items():
                        norm = normalise_label(lbl)
                        if (norm in FUNDING_ALIASES or "fund" in norm or "sponsor" in norm):
                            results[pkg].append((lbl, url))
            if use_remote:
                pypi_urls = query_pypi_project_urls(pkg)
                for lbl, url in pypi_urls.items():
                    norm = normalise_label(lbl)
                    if (norm in FUNDING_ALIASES or "fund" in norm or "sponsor" in norm):
                        if (lbl, url) not in results[pkg]:
                            results[pkg].append((lbl, url))
    else:
        dists = list(importlib_metadata.distributions())
        for dist in dists:
            name = dist.metadata.get("Name", dist.metadata.get("Summary", "Unknown"))
            funding_entries = extract_funding_urls_from_dist(dist)
            if funding_entries:
                results[name].extend(funding_entries)
            if use_remote and not funding_entries:
                pypi_urls = query_pypi_project_urls(name)
                for lbl, url in pypi_urls.items():
                    norm = normalise_label(lbl)
                    if (norm in FUNDING_ALIASES or "fund" in norm or "sponsor" in norm):
                        results[name].append((lbl, url))
    return results

def group_by_url(results: Mapping[str, List[Tuple[str, str]]]) -> Mapping[Tuple[str, str], List[str]]:
    grouped: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for pkg, entries in results.items():
        for lbl, url in entries:
            canon_url = normalise_url(url)
            grouped[(lbl, canon_url)].append(pkg)
    return grouped

def format_as_plain(results: Mapping[str, List[Tuple[str, str]]]) -> str:
    if not results:
        return (
            "No funding links found for any packages.\n"
            "This could mean:\n"
            "  - No packages declare funding links in their metadata.\n"
            "  - The packages use an older metadata format that doesn't support 'Project-URL'.\n"
            "  - The funding links are present but use a different, unrecognised label."
        )
    grouped = group_by_url(results)
    lines: List[str] = []
    lines.append("--- Funding Information Found ---")
    for (lbl, url), packages in sorted(grouped.items(), key=lambda kv: kv[0][1]):
        lines.append(f"{lbl}: {url}")
        lines.append("  Packages: " + ", ".join(sorted(packages)))
        lines.append("".join("-" for _ in range(30)))
    return "\n".join(lines)

def format_as_json(results: Mapping[str, List[Tuple[str, str]]]) -> str:
    grouped = group_by_url(results)
    jsonable = {
        f"{lbl}|{url}": {
            "label": lbl,
            "url": url,
            "packages": sorted(packages),
        }
        for (lbl, url), packages in grouped.items()
    }
    return json.dumps(jsonable, indent=2)

def format_as_markdown(results: Mapping[str, List[Tuple[str, str]]]) -> str:
    if not results:
        return "No funding links found."
    grouped = group_by_url(results)
    lines: List[str] = []
    lines.append("# Funding Information\n")
    for (lbl, url), packages in sorted(grouped.items(), key=lambda kv: kv[0][1]):
        lines.append(f"* **{lbl}**: {url}")
        lines.append(f"  - Packages: {', '.join(sorted(packages))}\n")
    return "\n".join(lines)

def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate funding links for Python packages by reading their metadata "
            "(and optionally PyPI project_urls).  Without arguments the script "
            "scans all installed distributions; otherwise supply package names to "
            "inspect them individually."
        )
    )
    parser.add_argument(
        "packages",
        nargs="*",
        help="Names of packages to inspect.  If omitted, all installed packages are scanned.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the results as JSON instead of human‑readable text.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output the results as Markdown instead of human‑readable text.",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Query the PyPI JSON API for packages (requires network and requests).",
    )
    return parser.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_arguments(argv)
    results = gather_funding_info(args.packages, use_remote=args.remote)
    if args.json:
        print(format_as_json(results))
    elif args.markdown:
        print(format_as_markdown(results))
    else:
        print(format_as_plain(results))

if __name__ == "__main__":
    main()
