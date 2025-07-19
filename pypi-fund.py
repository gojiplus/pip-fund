#!/usr/bin/env python3
"""
fund_py.py – Discover funding links for Python packages

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
* Providing optional JSON and Markdown output via ``--json`` and
  ``--markdown`` command‑line flags.  When neither flag is given, a
  human‑readable plain‑text report is produced.
* (Optional) Querying the PyPI JSON API for funding information when
  packages are not installed or to supplement local metadata.  Use
  ``--remote`` to enable this behaviour.  Note that network access is
  required and may fail when connectivity is unavailable.

This module is intended as an educational starting point.  It does not
cover every edge case and is not integrated with pip's dependency
resolution.  Contributions and enhancements are welcome; see the
project README for more ideas.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

try:
    # importlib.metadata is in the standard library for Python 3.8+
    from importlib import metadata as importlib_metadata  # type: ignore
except ImportError:
    # importlib_metadata backport for earlier versions
    import importlib_metadata  # type: ignore

# Try to import requests only if remote lookups are requested.  We
# declare a sentinel here to avoid failing if requests is missing and
# ``--remote`` isn't used.
try:
    import requests  # type: ignore[import]
except ImportError:
    requests = None  # type: ignore[assignment]

# Known funding aliases from the Python packaging spec.  When matching
# labels we normalise them first, then compare against this set.  You
# can add further aliases (e.g. "support", "backers") here.
FUNDING_ALIASES: set[str] = {
    "funding",
    "sponsor",
    "donate",
    "donation",
}

def normalise_label(label: str) -> str:
    """Normalise a Project‑URL label for comparison.

    The Python packaging specification recommends normalising by
    removing punctuation and whitespace and converting to lowercase
    before comparing labels:contentReference[oaicite:1]{index=1}.  This helps
    treat variants like "Sponsor this project" and "Fund" as the same.

    Args:
        label: The label from a Project‑URL entry.

    Returns:
        The normalised label.
    """
    # Remove all non‑alphanumeric characters
    cleaned = re.sub(r"[^A-Za-z0-9]", "", label)
    return cleaned.lower()


def extract_funding_urls_from_dist(dist: importlib_metadata.Distribution) -> List[Tuple[str, str]]:
    """Extract funding URLs from a distribution's metadata.

    Args:
        dist: An importlib.metadata Distribution object.

    Returns:
        A list of ``(label, url)`` pairs for any funding‑related Project‑URL
        entries found.  The label is the original (not normalised) label
        from metadata when available; for entries without a label
        (unlikely for funding) the label will be ``"Generic Link"``.
    """
    funding_entries: List[Tuple[str, str]] = []
    try:
        project_urls = dist.metadata.get_all("Project-URL", []) or []
    except Exception:
        project_urls = []
    for url_entry in project_urls:
        # According to the packaging spec, entries are "Label, URL"
        if "," in url_entry:
            label, url = url_entry.split(",", 1)
            label = label.strip()
            url = url.strip()
            norm = normalise_label(label)
            if (norm in FUNDING_ALIASES
                    or "fund" in norm
                    or "sponsor" in norm):
                funding_entries.append((label, url))
        else:
            # If no comma present, treat the entry as just a URL.  We
            # still check whether it contains "fund" or "sponsor" to
            # avoid unrelated links.
            url = url_entry.strip()
            if re.search(r"fund|sponsor", url, re.IGNORECASE):
                funding_entries.append(("Generic Link", url))
    return funding_entries


def query_pypi_project_urls(package_name: str) -> Dict[str, str]:
    """Query the PyPI JSON API for a package's project URLs.

    When ``--remote`` is specified, this helper uses the public PyPI
    JSON API at ``https://pypi.org/pypi/<package>/json`` to retrieve
    the ``project_urls`` mapping.  The API returns a dictionary of
    well‑known URLs, including a possible "Funding" entry:contentReference[oaicite:2]{index=2}.

    Args:
        package_name: The name of the package on PyPI.

    Returns:
        A mapping of ``{label: url}``.  An empty dict is returned if
        the package does not exist or an error occurs.  Requires
        ``requests`` to be installed.
    """
    if requests is None:
        return {}
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            project_urls: Mapping[str, str] = data.get("info", {}).get("project_urls", {}) or {}
            # Ensure keys and values are strings
            return {str(k): str(v) for k, v in project_urls.items() if k and v}
    except Exception:
        pass
    return {}


def gather_funding_info(package_names: Iterable[str], use_remote: bool) -> Dict[str, List[Tuple[str, str]]]:
    """Gather funding information for the given packages.

    Args:
        package_names: An iterable of package names to inspect.  If
            empty, the function will iterate over all installed
            distributions.
        use_remote: Whether to query PyPI for additional funding info
            (requires network access and requests).

    Returns:
        A dictionary mapping each package name to a list of ``(label, url)``
        pairs representing funding links.
    """
    results: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    if package_names:
        # Only inspect named packages.  For each, try to get its
        # distribution object; fall back to remote metadata if
        # installed distribution is not found.
        for pkg in package_names:
            try:
                dist = importlib_metadata.distribution(pkg)
                results[pkg].extend(extract_funding_urls_from_dist(dist))
            except importlib_metadata.PackageNotFoundError:
                # Not installed; if remote queries are allowed, try
                # PyPI JSON API
                if use_remote:
                    for lbl, url in query_pypi_project_urls(pkg).items():
                        norm = normalise_label(lbl)
                        if (norm in FUNDING_ALIASES
                                or "fund" in norm
                                or "sponsor" in norm):
                            results[pkg].append((lbl, url))
            # Optionally supplement with remote metadata even if the
            # package is installed: PyPI might have additional links not
            # packaged locally.  This can be toggled off by setting
            # use_remote=False.
            if use_remote:
                pypi_urls = query_pypi_project_urls(pkg)
                for lbl, url in pypi_urls.items():
                    norm = normalise_label(lbl)
                    if (norm in FUNDING_ALIASES
                            or "fund" in norm
                            or "sponsor" in norm):
                        # Avoid duplicates
                        if (lbl, url) not in results[pkg]:
                            results[pkg].append((lbl, url))
    else:
        # No package names given; scan all installed distributions
        dists = list(importlib_metadata.distributions())
        for dist in dists:
            name = dist.metadata.get("Name", dist.metadata.get("Summary", "Unknown"))
            funding_entries = extract_funding_urls_from_dist(dist)
            if funding_entries:
                results[name].extend(funding_entries)
            # Optionally check remote metadata for packages with no local
            # funding links.  This can be slow if there are many
            # distributions, so only do it if explicitly requested.
            if use_remote and not funding_entries:
                pypi_urls = query_pypi_project_urls(name)
                for lbl, url in pypi_urls.items():
                    norm = normalise_label(lbl)
                    if (norm in FUNDING_ALIASES
                            or "fund" in norm
                            or "sponsor" in norm):
                        results[name].append((lbl, url))
    return results


def format_as_plain(results: Mapping[str, List[Tuple[str, str]]]) -> str:
    """Format the funding results as a human‑readable string.

    Args:
        results: Mapping from package name to list of ``(label, url)`` pairs.

    Returns:
        A string representing the formatted report.
    """
    if not results:
        return (
            "No funding links found for any packages.\n"
            "This could mean:\n"
            "  - No packages declare funding links in their metadata.\n"
            "  - The packages use an older metadata format that doesn't support 'Project-URL'.\n"
            "  - The funding links are present but use a different, unrecognised label."
        )
    lines: List[str] = []
    lines.append("--- Funding Information Found ---")
    for pkg, entries in sorted(results.items()):
        lines.append(f"Package: {pkg}")
        for lbl, url in entries:
            lines.append(f"  {lbl}: {url}")
        lines.append("".join("-" for _ in range(30)))
    return "\n".join(lines)


def format_as_json(results: Mapping[str, List[Tuple[str, str]]]) -> str:
    """Format the funding results as a JSON string.

    Args:
        results: Mapping from package name to list of ``(label, url)`` pairs.

    Returns:
        A JSON string where each package name maps to an array of objects
        with ``label`` and ``url`` fields.
    """
    jsonable = {
        pkg: [
            {"label": lbl, "url": url}
            for lbl, url in entries
        ]
        for pkg, entries in results.items()
    }
    return json.dumps(jsonable, indent=2)


def format_as_markdown(results: Mapping[str, List[Tuple[str, str]]]) -> str:
    """Format the funding results as a Markdown string.

    The Markdown lists packages and their funding links.  Long lines are
    avoided in tables as per general Markdown guidelines.

    Args:
        results: Mapping from package name to list of ``(label, url)`` pairs.

    Returns:
        A Markdown‑formatted string.
    """
    if not results:
        return "No funding links found."
    lines: List[str] = []
    lines.append("# Funding Information\n")
    for pkg, entries in sorted(results.items()):
        lines.append(f"## {pkg}\n")
        for lbl, url in entries:
            # Use a simple list rather than a table to avoid long lines
            lines.append(f"* **{lbl}**: {url}")
        lines.append("")
    return "\n".join(lines)


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command‑line arguments.

    Args:
        argv: Optional list of arguments to parse (for testing).  If
            ``None``, defaults to ``sys.argv[1:]``.

    Returns:
        Namespace of parsed arguments.
    """
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


