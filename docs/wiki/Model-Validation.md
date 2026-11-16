# Validate and interpret a model

Review the scientific model before relying on a successful calculation. The native checker can detect many structural and expression errors; it cannot establish that the chosen perspective, evidence, comparator or clinical assumptions are appropriate.

Check the population basis, time horizon, cycle length, currency/year, outcome units and discounting. Use consistent per-person or programme-wide denominators. Do not convert unrelated cohorts into a probability distribution or double-count programme overhead and per-person costs. Chance siblings must be exhaustive and their probabilities sum to one; decision alternatives do not carry chance weights.

Review image transcriptions and workbook formula/cached-value differences. Intake inventories formulas; it is not an Excel recalculation engine. A broken `#REF!` is unresolved evidence, not permission to invent a repair. OCR is proposed extraction and needs review; unreadable pages stay unresolved.

Amua 3.2.4 preserves supported native variable updates and other native model fields during reviewed edits. Unsupported changes to simulation settings, tables, variables, constraints, topology or outcome dimensions may require the manual editor. Older AI-created files are not silently repaired: inspect them for values placed in fields ignored by the original engine.

Unknown scientific inputs and unreviewed image-derived values block calculations. Structure confirmation does not approve numerical inputs. Verify all unresolved questions before approving structure, then review the numerical source values separately. Use full model validation, run and inspect the completed console output. Save to a new file and retain the evidence/assumptions needed to reproduce the result.

An ICER is an incremental ratio. It does not establish affordability, clinical appropriateness or the optimal strategy without the relevant threshold and decision context. Review dominance, uncertainty and alternative assumptions before interpreting the result.
