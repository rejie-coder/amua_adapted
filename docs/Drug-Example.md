# Drug A and Drug B decision tree

The example table contains four terminal outcomes:

| Strategy | Outcome | Probability | Cost dollars | QALYs |
| --- | --- | ---: | ---: | ---: |
| Drug A | Success | 0.70 | 1000 | 2.0 |
| Drug A | Failure | 0.30 | 500 | 0.5 |
| Drug B | Success | 0.60 | 2000 | 3.0 |
| Drug B | Failure | 0.40 | 800 | 1.0 |

Create a decision root, a chance node for each drug and two terminal outcomes under each drug: seven nodes in total. Keep Cost and Effectiveness as separate outcome dimensions. Strategy alternatives do not have chance probabilities; their outcome branches do.

The native engine expects terminal outcomes in payoff fields. Put cost into the Cost payoff dimension and QALYs into the Effectiveness payoff dimension; terminal cost arrays stay zero. Do not assign a nonzero root cost or nonterminal payoff, which the engine would ignore.

Expected values are:

- Drug A: `0.70 × 1000 + 0.30 × 500 = 850`; `0.70 × 2.0 + 0.30 × 0.5 = 1.55` QALYs.
- Drug B: `0.60 × 2000 + 0.40 × 800 = 1520`; `0.60 × 3.0 + 0.40 × 1.0 = 2.20` QALYs.
- Incremental B versus A: cost `670`, effect `0.65`, ICER `1030.76923077` dollars per additional QALY.

The local controlled image/helper/sidebar tests reproduce these values through the original engine. Their remote response is a fixture; this does not prove live recognition of arbitrary images.

The table omits the time horizon, perspective, exact dollar currency/year and willingness-to-pay. Row values are treated as total outcomes per person and each pair of branches as exhaustive/mutually exclusive. These assumptions need confirmation. Drug A is the incremental reference, not a confirmed clinical standard. Native WTP zero is an unconfirmed software placeholder; do not accept the root's automatic preferred-drug choice until the real threshold and context are supplied.
