import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
from pathlib import Path
import numpy as np
from portfolio.core import make_catalog
from portfolio.chunk import process
from portfolio.aggregate import aggregate


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--outdir',default='demo_output')
    p.add_argument('--n',type=int,default=600)
    p.add_argument('--chunks',type=int,default=4)
    p.add_argument('--trials',type=int,default=12)
    a=p.parse_args(); out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    xy,value=make_catalog(n=a.n)
    catalog=out/'catalog.npz'
    np.savez_compressed(catalog,xy=xy,value=value)
    for i in range(a.chunks):
        process(catalog,out/'chunks'/f'chunk_{i:04}.npz',i,a.chunks,trials=a.trials)
    counts,means,cov=aggregate(out/'chunks',out)
    print(f'Processed {counts.sum():,} unique pairs across {a.chunks} chunks')
    print(f'Output: {out.resolve()}')

if __name__ == '__main__':main()
