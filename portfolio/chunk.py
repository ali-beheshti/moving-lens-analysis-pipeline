"""Command-line chunk worker for synthetic point catalogs."""
import argparse
from pathlib import Path
import numpy as np
from .core import chunk_stat, trial_permutation


def process(catalog, output, chunk_index, chunks, seed=123, trials=20, edges=None):
    data = np.load(catalog)
    xy, value = data['xy'], data['value']
    edges = np.asarray(edges if edges is not None else [0.02, 0.05, 0.1, 0.2, 0.35])
    observed, counts = chunk_stat(xy, value, edges, chunk_index, chunks)
    nulls = []
    for trial in range(trials):
        perm = trial_permutation(len(value), seed, trial)
        sums, trial_counts = chunk_stat(xy, value, edges, chunk_index, chunks, perm)
        if not np.array_equal(trial_counts, counts):
            raise RuntimeError('null trial changed geometry')
        nulls.append(sums)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, observed=observed, counts=counts,
                        nulls=np.asarray(nulls).reshape(trials, -1), edges=edges,
                        chunk_index=chunk_index, chunks=chunks, trials=trials, seed=seed)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--chunk-index', type=int, required=True)
    p.add_argument('--chunks', type=int, required=True)
    p.add_argument('--trials', type=int, default=20)
    p.add_argument('--seed', type=int, default=123)
    args = p.parse_args()
    process(**vars(args))

if __name__ == '__main__':
    main()
