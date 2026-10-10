# Design notes

## Distributed calculation

Spatial queries use a `cKDTree` built from the full synthetic catalog. Each unordered pair `(i,j)` belongs to the anchor with `i < j`. Deterministic modulo partitioning of `i` across worker jobs guarantees each pair is counted once and does not require inter-worker communication.

For each radial bin, workers return **sum of scalar products and integer pair count**. Aggregation sums these separately before division; averaging chunk means would produce a biased result when chunks contain different pair counts.

## Null test

All workers independently regenerate the same global permutation for each trial from a deterministic seed. Workers apply that permutation to the synthetic scalar field (not positions). Aggregation therefore builds one coherent global null realization per trial rather than combining unrelated shuffles. The covariance across trials uses the unbiased sample covariance (`ddof=1`).

## Practical caveats

This reference implementation prioritizes clarity over maximum throughput. Tree rebuilding and global-array loading per worker would need reengineering at very large scale; dense samples can produce O(N²) pairs. For reliable covariance estimation, use a sufficient number of null realizations and check numerical convergence.
