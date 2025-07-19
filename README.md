# pip‑fund

pip‑fund is a small command‑line tool that scans your Python environment (or a list of package names) and reports any funding or sponsorship links it can find. It is inspired by Node.js's `npm fund` command and uses Python's packaging metadata to discover funding information. The goal is to make it easy for developers to discover how to support the open‑source libraries they depend on.

## Features

**Normalizes labels and URLs**: Funding links are detected by examining Project‑URL metadata and matching normalized labels against a set of known aliases such as funding, sponsor, donate and donation. Labels containing the words fund or sponsor are also matched. Query strings and fragments are stripped from URLs before grouping, so links that differ only by tracking parameters are treated as the same.

**Groups duplicate links**: When multiple packages share the same funding URL, the tool groups them into a single entry and lists all associated package names.

**Multiple output formats**: Choose human‑readable text (default), JSON (`--json`) or Markdown (`--markdown`).

**Remote lookups**: Use the `--remote` flag to query the PyPI JSON API for funding links of packages that are not installed locally.

**Optional GitHub sponsor support**: When installed with the github extra (`pip install pip‑fund[github]`), the tool can attempt to fetch sponsor links from a repository's `.github/FUNDING.yml` file on GitHub if no funding metadata is present. This requires a GitHub access token.

## Installation

### Basic usage

```bash
pip install pip-fund

# Scan all installed packages for funding information
pip-fund

# Check specific packages (installed or not) and query PyPI if needed
pip-fund --remote requests flask

# Output Markdown instead of plain text
pip-fund --markdown
```

### Enabling GitHub sponsor integration

To enable GitHub sponsor discovery, install the github extra and provide a GitHub personal access token via the `GITHUB_TOKEN` environment variable. Without a token the GitHub API will operate with very limited rate limits.

```bash
pip install pip-fund[github]

export GITHUB_TOKEN=ghp_yourtokenhere
pip-fund --github flask
```

## Usage

Running `pip-fund` without arguments scans all installed distributions in the current Python environment. For each unique funding link found, it prints the label, the URL and the names of packages that declare it. If no funding information is discovered, the tool explains why this might be the case.

Use the `--json` or `--markdown` flags to produce machine‑readable output. Combine `--remote` with package names to query funding information for packages that aren't installed.

## Project structure

This project follows the modern Python packaging guidelines:

A `pyproject.toml` file declares the build system (setuptools) and metadata such as the project name, version and console script entry point. The `[project.scripts]` table instructs the build backend to generate a `pip-fund` command that invokes the `main()` function in `pip_fund/fund.py` [packaging.python.org](https://packaging.python.org).

Source code lives in the `src/pip_fund/` package. The main module `fund.py` implements the logic of detecting funding links.

Optional dependencies for GitHub sponsor support are defined under `[project.optional-dependencies]` in `pyproject.toml`. Installing with `pip install pip-fund[github]` adds the PyGithub and PyYAML libraries.

## Contributing

Contributions are welcome! Feature requests, bug reports and pull requests are greatly appreciated. Areas of interest include:

- Improving detection of funding links in package metadata
- Supporting additional donation platforms
- Enhancing the GitHub sponsor integration
- Adding interactive prompts or browser integration to open funding pages directly from the CLI

## License

This project is released under the MIT License.

---

## Implementation Details

**fund.py** contains the complete implementation. It normalizes labels and URLs, groups identical funding links across packages, supports JSON/Markdown output, queries PyPI for remote packages, and optionally fetches sponsor links from GitHub's `.github/FUNDING.yml` when the github extra is installed.

You can extract the tarball, inspect the files, and run the tool directly with:

```bash
tar -xzf pip_fund_package.tar.gz
python pip_fund/src/pip_fund/fund.py --help
```

or install it locally in editable mode (assuming network access for setuptools is available):

```bash
cd pip_fund
python -m pip install -e .        # install with basic features
python -m pip install -e .[github]  # install with optional GitHub support
pip-fund                           # run the installed command
```

Remember to set `GITHUB_TOKEN` before using the `--github` flag.