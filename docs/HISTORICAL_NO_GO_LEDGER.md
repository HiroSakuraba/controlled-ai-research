# Historical no-go ledger

This ledger records limitations established by the finite prototype. It is not a
claim that the corresponding idea is impossible in every environment.

| Direction | Result | Reason | Status |
| --- | --- | --- | --- |
| Count operations rather than complete exports | Fails | A single release can concentrate risk across arbitrarily many artifacts. | Do not use |
| Revoke actor access and declare the episode safe | Fails | A pending delayed effect can still execute after revocation. | Do not use |
| Local executor effects table as exactly-once external delivery | Fails | SQLite cannot atomically commit a remote effect. | Do not use |
| Single monitor channel as a general control | Fails in the fixture suite | Each of the four attacks bypasses an unmatched channel. | Retain only as an ablation |
| Post-selection rejection or free resampling | Invalidates the stated sampler comparison | Conditioning can increase probability concentration. | Do not use without a new proof |
| Use model-reported probabilities as the controller's accounting source | Not justified | A model can misreport or omit them. | Do not use |
| Treat long or wandering reasoning as evidence of deception | Not justified | Difficulty produces the same signal. | Use only as a trigger for another check |
| Interpret finite solver performance as model-attacker performance | Invalid | It is an exact capability ceiling only for the toy state space. | Keep as benchmark only |

Reconsider an entry only with a changed formal model, a new proof, and a test
that distinguishes the revised claim from the failed one.
