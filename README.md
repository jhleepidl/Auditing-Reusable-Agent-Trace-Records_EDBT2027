# Auditing Reusable Agent Trace Records

Reproducibility package for **Auditing Reusable Agent Trace Records: Provenance, Versioning, and Executable Partial Contracts**.

The package contains the inputs and code needed to regenerate the main contract results, together with the original checkpoint observations and timing samples. Large prediction, diagnostic, compiled-contract, and bootstrap output files are **not** distributed. The reproduction command creates them in a new directory and checks compact publication metrics and output digests.

## Run the artifact

Use Python 3.11 or later. The tested portable environment is Python 3.13.5 with `jsonschema==4.26.0`.

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python reproduce.py --output ../trace-audit-output
```

Allow several minutes and approximately 2 GB of free working space. No API key, GPU, model service, or AgentDojo installation is needed for this command. Installing the dependency may require Internet access; reproduction itself does not make provider calls. `--cpu` is an optional alias for the default mode.

A successful run prints `PASS` and writes `summary.json`. Each run requires a **new directory outside the artifact**. Existing evidence or output is never overwritten. Do not run Python with `-O`: the frozen scientific engines use assertions to validate inputs.

For a quick, standard-library-only check:

```sh
python reproduce.py --check-only --output ../trace-audit-quick
```

This quick mode verifies files and recomputes checkpoint/read comparisons, census fractions, and cost aggregates from retained observations. It does **not** execute contract candidates. The full default run adds 98 scientific regression tests, release tests, **53,248 frontend prediction cells**, and **768 initial/corrected capability-control cells**.

## What to inspect

| Generated path under the output directory | Paper content |
|---|---|
| `tables/table3_census.csv` | Table 3: retained-corpus fidelity and eligible suffix counts |
| `tables/checkpoint_recovery.csv` | Table 4: six readers on 36 checkpoints |
| `tables/read_recovery.csv` | Figure 3(b): 12 appended native reads |
| `tables/warm_costs.csv` | Table 5: medians of recorded timing and size samples |
| `tables/table6_one_call.csv` | Table 6: literal/program comparison |
| `tables/table7_review.csv` | Table 7: first call, review-only, and feedback |
| `tables/table8_frontend_retention.csv` | Table 8: ordering/addressing interventions |
| `tables/frontend_metrics.csv` | All model, method, stage, and frontend metrics |
| `checkpoint/` | Regenerated checkpoint comparison rows and census metrics |
| `cpu/results/` | Regenerated predictions, diagnostics, constructions, deltas, and statistics |
| `cpu/verification.json` | Generated-file checks and original test counts |
| `summary.json` | Overall status and the verification scope actually completed |

`--check-only` produces only checkpoint/census/cost tables; it does not copy cached contract tables. Default-mode tables use freshly regenerated predictions. Scoring reads reference judgments after predictions have been produced. Expected metrics and digests are comparison targets, not inputs to candidate execution.

The expected checkpoint continuation counts are **13/36 for type + order, 25/36 for constructor restoration, and 36/36 for both the captured witness and trusted pickle**. Appended native read agreement is **3/12 versus 12/12** for constructor and captured-witness restoration. These are finite, exposed programs, not full-task semantic judgments.

For one-call program construction, valid retention is:

| Frontend | GPT-5.4 mini | GPT-6 Luna provider alias |
|---|---:|---:|
| Original | 6.94% | 33.33% |
| DAG ordering | 8.33% | 33.33% |
| Metadata addressing | 18.06% | 34.72% |
| Both | 19.44% | 34.72% |

Literal retention remains 86.11% and 93.06%. No program false passes or UNKNOWN-reference promotions occur in these tested comparisons. Failures, all four frontend policies, baseline candidates, and the initial arithmetic-control error remain in the reproduction workload; compact packaging does not select favorable cases.

## Code and inputs

```text
README.md          all installation and use instructions
reproduce.py       review entry point
requirements.txt   portable CPU dependency
code/              scientific engines, regression tests, and reproduction drivers
data/              retained sources, observations, requests, model responses, and controls
configs/           study plans, environment pins, immutable input bindings
expected/          compact publication metrics and regenerated-output checksums
tests/             packaging and output-safety tests
third_party/       pinned benchmark source and license
NOTICE             attribution and distribution scope
checksums.sha256   release inventory
```

Start with `data/checkpoint/corpus/F09/` and `F10/` for the value-identical checkpoint example, and `data/checkpoint/reads/C03/` for the observed read difference. Model requests and responses are under `data/contracts/`; `code/frontend/method/frontend.py` contains the two mechanical frontend interventions. The interpreter is `code/contracts/interpreter/contract_executor.py`.

Several original inputs have identical bytes. The release stores one copy and records aliases in `configs/input_layout.json`; larger JSON files use lossless gzip transport. The launcher verifies compressed and logical bytes and automatically restores the original import/input layout in a temporary working directory. No manual path configuration, Git LFS, or bulk result download is needed. This is path relocation and storage deduplication, not normalization of experimental data. Frozen source code and request/response bytes retain their original hashes.

## Scope of reproduction

- **Checkpoint/read evidence:** the portable workflow compares retained native and restored states, graph witnesses, and tool returns. It recomputes 216 checkpoint comparisons and 24 read comparisons. It does not freshly execute tools. Table 3 is reaggregated from per-record native execution receipts; exact-label and state-hash consistency are checked.
- **Timing:** 1,512 original paired measurements are retained because they are the evidence for the paper's measurements. The code recomputes the medians. New measurements on different hardware are a separate experiment.
- **Frozen contracts:** the complete six-stage, four-policy workload regenerates prediction/diagnostic files and compiled payloads. Output digests cover exact prediction/diagnostic bytes and compiled payloads with only `compile_ms` excluded. Task statistics are checked with a tolerance solely for floating-point rounding. The old-policy baseline for deltas is generated in the same run; there is no hidden cached-prediction dependency.
- **Supporting studies:** the compatible and failed common-scope pilot retain selected requests, responses, references, observations, and code for inspection, but are not part of the default 54,016-cell replay. Earlier checkpoint/source material and compact supporting summaries remain available. Complete original raw records for the earliest 4,104-case controlled study, BFCL/tau-bench adapter and 36-task probe, and 48/96-request interface studies were not provided in the original archive. Their summaries are not presented as independently rerunnable raw experiments.

False-pass uses FAIL-reference cases; retention uses PASS-reference cases. Errors and UNKNOWNs remain in the denominators. Repetitions and source worlds are averaged within task before averaging tasks; the source study has eight exposed templates. Extra worlds or calls do not create independent tasks.

References are machine-authored necessary conditions within a selected scope, not human semantic gold. Model responses, reference builders, and authored capability controls serve different roles. Capability controls and frontend repairs used coding-assistant support. Both the initial 380/384 arithmetic-control result and the corrected 384/384 result are regenerated; the correction remains development, not a new untouched confirmation.

## Optional native rerun

A separate environment with **Python 3.11.7** and the original 75 pins is required. The benchmark revision is `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.

```sh
python -m pip install -r configs/environment/native-requirements.lock
python reproduce.py --native --output ../trace-audit-native
# Optional new measurements, not a replacement for the original timing samples:
python reproduce.py --timings --output ../trace-audit-new-timings
```

The native mode executes the original checkpoint readers and native tool programs, and compares new observations with the retained evidence. The packaging driver validates the selected executable dependencies and exact environment instead of requiring obsolete whole-archive outputs. Scientific reader, benchmark, and plan bytes are unchanged. A missing or different pin returns `BLOCKED`, not successful reproduction. The positive native path has not been rerun in the packaging environment; the portable modes have.

Trusted pickle is created only from the live object constructed locally by the native benchmark harness. Never substitute an external pickle payload. Portable reproduction reads JSON only. Captured witnesses cover declared fields, modeled containers, concrete types, order, and sharing, not arbitrary globals or external services.

## Integrity and distribution

Exit 0 is success, 1 a verification failure, 2 an invalid argument/output path, and 3 a blocked native environment. Keep logs when a comparison fails; do not disable checks or change expected values to force a pass. Git line-ending conversion is disabled through `.gitattributes` to preserve input hashes. After using a hosting or anonymization service, test its actual downloaded copy before submission.

Experimental outputs are created outside the submitted tree. The internal research archive is not replaced by this lean package: recoverable bulk predictions, repeated generated summaries, old build products, and redundant run logs are omitted, while the inputs needed for the declared replay and compact validation targets are retained. Source hashes establish file consistency, not authentic external collection.

See [NOTICE](NOTICE) and the benchmark's [license](third_party/agentdojo/LICENSE). No provider credentials, installed environment, or font files are bundled; benchmark account and email strings are fixture data. No blanket license is assigned to third-party material.
