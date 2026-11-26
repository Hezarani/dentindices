# Contributing to DentIndices

Thank you for helping. DentIndices is only useful if its rules are right, so the most valuable
contributions are **corrections backed by a source**.

## Reporting a rule that looks wrong

Open an issue with:

1. the index and the function (for example `bewe_from_teeth()`),
2. the input you used and the result you expected,
3. the publication, page or table that supports your expectation.

If sources disagree, say which ones; the decision will be recorded in the `discrepancies` section of
`dentindices/data/indices.json` either way.

## Adding or changing an index

- Put codes, thresholds and bands in `dentindices/data/indices.json`, with a source entry
  (authors, year, title, journal, DOI) and a verification note.
- Implement the rule in the Python module **and** in `docs/dentindices.js`, using the same names and
  the same order of warnings and trace lines.
- Add tests in `tests/`, including a worked example from the source when it has one, and add the
  function to the random parity cases in `tests/test_web_engine.py`.
- Run `python scripts/build_web_data.py` to refresh the web app's data files, then
  `python -m pytest` (Node.js 18 or later is needed for the parity tests).

## Data

Never commit real patient data or copyrighted PDFs. Example files must be synthetic
(`scripts/make_examples.py`).
