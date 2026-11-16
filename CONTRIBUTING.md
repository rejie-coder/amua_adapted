# Contributing

Report reproducible issues with app version, operating system, architecture, expected/actual behavior and a synthetic minimal model. Do not attach credentials, patient data or confidential workbooks. For a security issue use [SECURITY.md](SECURITY.md).

Read the [build instructions](docs/Building.md) and [release limitations](docs/Release-Notes-3.2.4.md). Preserve original notices and numerical behavior. Keep scientific unknowns unresolved, retain native model fields and Undo/Redo, and never invent a missing source value to make a test pass. Test original model validation/calculation as well as UI state when changing model conversion.

Use a branch and pull request. Describe the concrete failure, resulting behavior and tests. Separate synthetic service/clipboard checks from real account/desktop evidence. A passing parser test alone is insufficient for a scientific modelling change.
