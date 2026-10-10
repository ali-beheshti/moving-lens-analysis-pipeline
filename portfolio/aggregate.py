"""Combine chunk outputs and write statistical summaries."""
import argparse
from pathlib import Path
import numpy as np


def aggregate(input_dir, output_dir, plot=True):
    files = sorted(Path(input_dir).glob('chunk_*.npz'))
    if not files:
        raise ValueError('no chunk files')
    chunks = [dict(np.load(path)) for path in files]
    n = int(chunks[0]['chunks'])
    ids = [int(c['chunk_index']) for c in chunks]
    if sorted(ids) != list(range(n)) or len(chunks) != n:
        raise ValueError('missing, extra, or duplicate chunks')
    for c in chunks[1:]:
        if any(not np.array_equal(c[k], chunks[0][k]) for k in ('edges', 'chunks', 'trials', 'seed')):
            raise ValueError('incompatible chunk settings')
    edges = chunks[0]['edges']
    sums = sum((c['observed'] for c in chunks))
    counts = sum((c['counts'] for c in chunks))
    null_sums = sum((c['nulls'] for c in chunks))
    mean = np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts>0)
    null = np.divide(null_sums, counts[None, :],
                     out=np.full_like(null_sums, np.nan), where=counts[None, :]>0)
    if np.any(counts == 0):
        raise ValueError('empty bins; change the synthetic catalog or edges')
    cov = np.cov(null, rowvar=False, ddof=1) if len(null)>1 else np.full((len(counts),len(counts)),np.nan)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    np.savetxt(out/'summary.csv', np.column_stack([edges[:-1],edges[1:],counts,mean,
                    np.sqrt(np.diag(cov))]), delimiter=',',
               header='r_min,r_max,pair_count,toy_mean,null_std', comments='')
    np.savetxt(out/'null_covariance.csv', cov, delimiter=',')
    if plot:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            centers = (edges[1:]+edges[:-1])/2
            fig,ax = plt.subplots(figsize=(7,4))
            ax.errorbar(centers,mean,yerr=np.sqrt(np.diag(cov)),fmt='o-',capsize=3)
            ax.axhline(0,ls=':',color='gray')
            ax.set(xlabel='Synthetic 2D separation (arbitrary units)',
                   ylabel='Toy centered pair product (arbitrary units)',
                   title='Spatial pair statistics')
            fig.tight_layout();fig.savefig(out/'summary.png',dpi=170);plt.close(fig)
        except ImportError:
            pass
    return counts, mean, cov


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir',required=True)
    p.add_argument('--output-dir',required=True)
    args=p.parse_args()
    aggregate(**vars(args))

if __name__ == '__main__': main()
