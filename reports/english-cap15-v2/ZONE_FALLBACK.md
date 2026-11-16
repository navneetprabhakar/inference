# Reviewed zone fallback after provider capacity failure

The first create operation completed with ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS. Provider explicitly identifies us-central1-a as having capacity. This is a new reviewed one-shot fallback, not an automatic retry of the closed request. Latest user's hands-off $15 authorization covers A100 selection; no further budget or quality change is inferred.

Before fallback: require first operation DONE with capacity failure, exact instance absent, no disk with that name, and no running project VM. Close first ledger reservation with zero observed compute and preserve full operation evidence. Use same A100 type/region/list rate and same original absolute termination timestamp18:13:22UTC. No extra runtime, no budget reset, same immutable worker/input hashes. At most one fallback; another failure ends this campaign attempt. The previous PLAN's no-automatic-fallback rule remains: this separate evidence-backed review precedes action.

The packet retains its original run ID/GCS namespace; no worker ran and that output namespace is unused. Fallback VM name adds -a; model/run identity and input receipt remain unchanged. Ledger binds both VM names to the original experiment. Existing models and frozen files remain untouched.
