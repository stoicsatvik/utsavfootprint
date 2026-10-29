# E392: same-source replay amplification in hotspot fusion

Date: 2026-10-29. **Synthetic software experiment, not field evidence.**

## Question and preregistered invariant

Does repeating an identical report from one `source_id` alter the fused
location, material probability or mass estimate when no independent
measurement has been added? The falsifiable invariant is that these three
quantities should be unchanged under identical same-source replay. Raw
observation count and observation IDs may increase.

## Frozen fixture and observed failure

Three independent synthetic sources A/B/C, equal timestamps, confidence and
quality; latitudes 19.07600/19.07605/19.07610 degrees, longitude 72.8777.
Plastic probabilities 0/0.5/1; mass-low values 10/20/30 kg with high=low+2.
Eight additional identical C reports were inserted with distinct observation
IDs but the same source identity and payload.

| Metric | Original 3 reports | 8 extra C replays | Expected |
|---|---:|---:|---|
| Independent source count | 3 | 3 | unchanged |
| Mass low (kg) | 20 | 30 | unchanged |
| Plastic probability | 0.5000 | 0.8636 | unchanged |
| Latitude (degrees) | 19.07605000 | 19.07608636 | unchanged |
| Approximate latitude displacement | 0 m | 4.04 m | 0 m |

The expected-red exact-head GitHub Actions run
[40883102094](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40883102094)
failed **exactly two new adversarial tests**; 32 inherited tests passed,
Ruff passed. The log directly records 30 != 20 and 0.8636 != 0.5.
This falsifies replay invariance in the prior fusion implementation.

## Correction and negative control

Select one deterministic strongest/freshest representative per `source_id`
for centroid and material fusion, and one per source after provenance-rank
filtering for the mass median. The existing confidence aggregator already
deduplicated by source; that behavior is retained. A separate fourth source
is a control: adding it *does* change the mass median from 20 to 25 kg and
raises the plastic probability, so the fix does not discard all new evidence.

- Test-first commit: `db0ebddb591fc6471721e035f3a53a39e4fd2813`
- Production correction: `1f92299f7b121936eef380b82b8b9bf9283836c9`
- Independent-source control: `50e90bea60a6106acf5586db5941069872f4d245`
- Corrected exact-head CI:
  [40883243231](https://github.com/stoicsatvik/utsavfootprint/actions/runs/40883243231),
  **SUCCESS**, Ruff clean, **35/35 pytest tests passed**.

## Scope and remaining falsifiers

**SUPPORTED IN TESTED SOFTWARE:** identical same-source replays no longer
amplify mass, material or centroid on this synthetic fixture.
**REJECTED:** the previous implementation's implicit replay invariance.
**NOT YET PROVEN:** physical pile identity, independent source authentication,
robustness to source-ID spoofing, sensor calibration, cross-time consistency,
or real-world waste mass and material accuracy.

Choosing one strongest report per source is a conservative heuristic.
Legitimate time-varying measurements can differ; no claim is made that the
selected report is ground truth. The E371 symmetry obstruction remains
unresolved. No live data, CCTV feeds, personal information, field samples,
or public deployment were used.

## Next decisive experiment

Use authorized, independently labelled same-pile vs different-pile
observations to quantify replay resistance, overmerge/oversplit errors and
source-identity spoofing sensitivity. Preregister abstention/error costs and
compare independent-source deduplication against timestamp-aware
within-source fusion under held-out spatial/time perturbations.
