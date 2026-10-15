# jev-benchmarks

Decision-model benchmarks, raw measurements and the generators for
[the published report](https://ai.vilinski.dev/jev-benchmark/) and
[the interactive model explorer](https://ai.vilinski.dev/decision-models/).
Extracted from [vilinski/jev](https://github.com/vilinski/jev); this repository
contains the benchmark, while `jev` contains the Rust CLI.

## Requirements

- Python 3.14 (standard library only; also configured in `mise.toml`).
- [jev](https://github.com/vilinski/jev) 0.4.1 or later for live inference.
  Install it with `cargo install --git https://github.com/vilinski/jev --locked`.
- macOS `sips` or Quick Look for regenerating preview PNGs. On other platforms,
  the generators reuse existing PNGs.

Run commands from this repository root. Analysis of saved results needs no API
keys or network access. Authenticate live calls with `jev login -p <provider>`;
Python never loads credentials. Set `JEV_BINARY` to select a particular binary.

## Rebuild the report

```sh
python3 report.py
```

This reads `model_registry.json`, saved `results/*.json` and `pricing/`, then
writes `report.html`, `data.json`, `statistics.csv`, `og.svg` and `og.png`.
The registry distinguishes each model and API route. The own set has 60 tasks
repeated three times; the public sample has 1,100 items across 22 datasets.
Partial direct Cloudflare runs, request errors, typed refusals, unsupported
questions and infrastructure exclusions are retained separately.

To build the whole website, supply the existing coding-agents page:

```sh
python3 site.py /path/to/coding-agents/index.html
# Optional second argument: the coding-agents updater template.
```

Output goes to ignored `site/`. `stage_site.py` can copy the two benchmark pages
and their downloads into a local `ai.vilinski.dev` checkout and produce an offline
preview. Publishing is a separate action; generators do not deploy anything.
See [AGENTS.md](AGENTS.md) for publication and SEO requirements.

## Run or resume measurements

Live runs cost money and use credentials held by `jev`:

```sh
python3 fetch_jevbench.py
python3 run_variants.py --help
python3 run_variants.py --all --workers 24
# Or choose explicit model/route combinations, as listed by --help.
```

`mise run bench` fetches the public data, resumes the registry runs, then builds
the report and website. Set `CODING_PAGE` to the coding-agents HTML path before
running its site task. `JEVBENCH_PER=50` selects 50 items per dataset.

Checkpoints are resumable and locked per route. Raw JSON results, including
historical runs and smoke checks, are versioned; lock files, logs, downloaded
dataset caches and generated website trees are ignored. Never replace missing
measurements with manufactured results. `run.py`, `run_hf.py` and `scoring.py`
are retained for historical context; use `run_variants.py` for current runs.

## Data and licenses

`dataset.py` defines the hand-labelled own set. The public sample comes from
[Praveenrajus/jev-bench](https://huggingface.co/datasets/Praveenrajus/jev-bench);
its component datasets have their own licenses, listed in the dataset manifest.
Downloaded test splits are cached locally and are not included in Git.
Raw measurement checkpoints retain sampled inputs for auditability and remain
subject to the corresponding dataset licenses. `pricing/` records dated pricing
sources, and `archive/` preserves historical report data.

Benchmark code is available under MIT OR Apache-2.0, inherited from `jev`.
