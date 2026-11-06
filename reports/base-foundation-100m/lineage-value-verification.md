# Lineage tensor-value verification

Result: **passed**.

Original seed **103**, recorded PyTorch **2.14.1**, and exact historical GPT2 source `d6116e2475eac590e8192f8391a59713c5ede157077117c4d59e559f38cf280c` were used to construct the model on CPU. All **148 tensors / 124,439,808 elements** were compared with the retained original zero-step checkpoint. Exact equality: **True**.

The live campaign zero-step model was compared with the protected `f029…` parent. All **148 tensors / 124,439,808 elements** were compared. Exact equality: **True**.

The run took **4.08 seconds**. Monitored peak RSS was **1620.1 MiB**. Child lifetime peak was **1620.1 MiB**. It used one CPU thread for PyTorch operations, with zero forward passes, training updates or GPU work.

The JSON records exact source/checkpoint paths, hashes, outcomes and limits. RSS sampling is approximate and macOS may treat RLIMIT_RSS as advisory. Local reproducibility establishes integrity and consistency, without independent attestation. The earlier metadata-only audit remains preserved. The first attempt stopped before construction because macOS rejected the RSS rlimit setting; the successful retry used the independent parent watchdog and checked the measured lifetime peak against the cap.
