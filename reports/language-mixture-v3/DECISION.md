# Decision: defer the 30M story / 30M web pilot

Root observed the following inventory across all 729,000 rows of the existing raw shard, using only publisher score and publisher token_count:

| Floating score threshold | Raw documents | Publisher tokens |
|---|---:|---:|
| >=4 | 15,212 | 16,002,260 |
| >=4.5 | 696 | 644,202 |
| >=5 | 3 | 1,962 |

These are root-reported upper inventories before previous-lineage exclusions, quality filters and custody. They are **not GPT2 token caps**: retokenization can change counts. They do not establish that this shard can supply 30M clean GPT2 web tokens.

Defer the proposed 30M/30M pilot. Do not lower thresholds, repeat documents, substitute stories or initiate fresh downloads to fill the quota. No additional data processing is authorized by this note. The next assigned review will concern a new SFT v3 candidate after root custody; wait for that notification.
