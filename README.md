# pypi fund

A simple script to enumerate funding links for installed Python packages, inspired by npm's npm fund.

## Background

Node.js's package manager includes an `npm fund` command that lists dependencies with funding URLs. This encourages developers to support the open‑source libraries they depend on.

Python packaging metadata has a similar concept: the core metadata specification lists well‑known labels for Project‑URL entries. The funding label—together with aliases such as sponsor, donate and donation—is designated to hold a package's funding information [packaging.python.org](https://packaging.python.org). The PyPI JSON API exposes these URLs under the project_urls dictionary; for example, the sample sampleproject metadata includes a `"Funding": "https://donate.pypi.org"` entry in [docs.pypi.org](https://docs.pypi.org).

GitHub also offers a `.github/FUNDING.yml` file to display sponsor buttons with multiple funding platforms [docs.github.com](https://docs.github.com). 

However, there is no built‑in `pip fund` command equivalent to `npm fund` that aggregates funding links from installed packages.

## What this script does

The provided script scans the current Python environment and prints any funding URLs found in installed packages. It works by:

- Using `importlib.metadata.distributions()` to iterate over installed distributions
- Reading each package's Project‑URL metadata
- Checking whether the label or URL indicates funding. It currently matches labels that equal funding or sponsor, or contain the substrings fund or sponsor
- Printing the project name, the matched label and the funding URL

Running the script in a typical environment might produce output like:

```yaml
Project: jupyter_server
  Funding: https://numfocus.org/donate
------------------------------
Project: jsonschema
  Funding: https://github.com/sponsors/Julian
------------------------------
```

## Ideas for improvement

The current proof‑of‑concept works, but there are several opportunities to make it more robust and useful:

1. Normalize labels and support all well‑known aliases

The Python packaging specification recommends normalizing Project‑URL labels by removing punctuation and whitespace and comparing lower‑cased strings [packaging.python.org](https://packaging.python.org).

Implementing the normalization function (as described in PEP 753) would allow labels like Funding, Donate or Sponsor this project to be treated the same. The specification also lists donate and donation as synonyms for funding; adding these to the match list will increase coverage.

2. Filter duplicates and improve presentation

At present every funding URL is printed separately, even if a package provides multiple funding‑related links. Group URLs per project and format the output more clearly (e.g. as a table or JSON), or support `--json` and `--markdown` flags.

3. Search remote metadata

Sometimes a library is not installed but still needs support. Add an option to query the PyPI JSON API for a given package name and extract `project_urls["Funding"]` [docs.pypi.org](https://docs.pypi.org).

This could let users run `python fund.py requests` to see the funding information for requests even if it isn't installed.

4. Surface GitHub Sponsor links

For packages hosted on GitHub that don't include funding metadata, use the GitHub API to look for a `.github/FUNDING.yml` file [docs.github.com](https://docs.github.com) or parse repository metadata. This requires an access token but could uncover additional funding options.

5. Integrate with pip

To truly mirror `npm fund`, package this utility as a pip plugin (e.g. `pip‑fund`) that hooks into pip's command‑line interface and reuses its dependency graph.

6. Configuration and caching

Provide a configuration file to ignore certain packages or group funding links by organisation (e.g. all Jupyter packages link to numfocus.org). Caching results can avoid re‑scanning the environment on every invocation.

7. Improve label matching

Label matching is simple and may miss non‑standard labels until normalization and alias support is implemented.

## Contributing

Contributions are welcome! You can improve the detection logic, add command‑line options, or expand the script to support other ecosystems. Please open issues or pull requests with suggestions.

## License

This project is released under the MIT License.
