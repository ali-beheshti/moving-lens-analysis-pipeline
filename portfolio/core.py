"""Radial pair-product statistics over two-dimensional point catalogs."""
import numpy as np
from scipy.spatial import cKDTree


def make_catalog(n=1000, seed=42):
    if n < 2:
        raise ValueError("n must be >= 2")
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, 1, size=(n, 2))
    # Smooth spatial variation with additive Gaussian noise.
    value = np.sin(3 * xy[:, 0]) + 0.4 * np.cos(5 * xy[:, 1])
    value += rng.normal(0, 0.6, n)
    return xy, value


def chunk_stat(xy, value, edges, chunk_index, chunks, permutation=None):
    """Sums/counts of centered scalar products for unordered spatial pairs.

    Each pair (i, j) is assigned to its lower-index anchor i; chunks partition
    anchors modulo chunks, so cross-boundary pairs aren't omitted or doubled.
    """
    xy = np.asarray(xy, dtype=float)
    value = np.asarray(value, dtype=float)
    edges = np.asarray(edges, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) != len(value):
        raise ValueError("invalid catalog shape")
    if not np.all(np.isfinite(xy)) or not np.all(np.isfinite(value)):
        raise ValueError("non-finite inputs")
    if edges.ndim != 1 or len(edges) < 2 or edges[0] <= 0 or not np.all(np.diff(edges) > 0):
        raise ValueError("edges must be increasing and positive")
    if chunks < 1 or not 0 <= chunk_index < chunks:
        raise ValueError("invalid chunk specification")
    if permutation is not None:
        permutation = np.asarray(permutation)
        if permutation.shape != (len(value),):
            raise ValueError("invalid permutation length")
        value = value[permutation]
    centered = value - value.mean()
    sums = np.zeros(len(edges)-1, dtype=float)
    counts = np.zeros(len(edges)-1, dtype=np.int64)
    tree = cKDTree(xy)
    for i in range(chunk_index, len(xy)-1, chunks):
        candidates = tree.query_ball_point(xy[i], r=float(edges[-1]))
        js = np.array([j for j in candidates if j > i], dtype=int)
        if not len(js):
            continue
        distance = np.linalg.norm(xy[js] - xy[i], axis=1)
        index = np.searchsorted(edges, distance, side='right')-1
        valid = (index >= 0) & (index < len(sums))
        np.add.at(sums, index[valid], centered[i] * centered[js[valid]])
        np.add.at(counts, index[valid], 1)
    return sums, counts


def trial_permutation(n, seed, trial):
    """Identical permutation for any job with the same seed/trial."""
    return np.random.default_rng(np.random.SeedSequence([seed, trial, 119])).permutation(n)
