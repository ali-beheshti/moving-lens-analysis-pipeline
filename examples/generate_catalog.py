import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
from pathlib import Path
import numpy as np
from portfolio.core import make_catalog

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--n',type=int,default=1000)
    p.add_argument('--seed',type=int,default=42)
    a=p.parse_args()
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    xy,value=make_catalog(a.n,a.seed)
    np.savez_compressed(out,xy=xy,value=value)
    print(f'Wrote {a.n} synthetic points to {out}')
