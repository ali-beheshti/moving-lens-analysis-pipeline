import tempfile
import unittest
from pathlib import Path
import numpy as np
from portfolio.core import make_catalog,chunk_stat,trial_permutation
from portfolio.chunk import process
from portfolio.aggregate import aggregate

class DemoTests(unittest.TestCase):
    def test_chunk_partition_equivalence(self):
        xy,val=make_catalog(60,7); edges=[0.01,0.1,0.3,0.6]
        entire,counts=chunk_stat(xy,val,edges,0,1)
        separate=[chunk_stat(xy,val,edges,i,5) for i in range(5)]
        np.testing.assert_allclose(entire,sum(x[0] for x in separate),rtol=1e-13,atol=1e-13)
        np.testing.assert_array_equal(counts,sum(x[1] for x in separate))

    def test_determinism(self):
        xy,val=make_catalog(30,2)
        np.testing.assert_array_equal(trial_permutation(30,4,0),trial_permutation(30,4,0))
        self.assertFalse(np.array_equal(trial_permutation(30,4,0),trial_permutation(30,4,1)))

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            xy,value=make_catalog(90,3)
            np.savez(root/'input.npz',xy=xy,value=value)
            for i in range(3):
                process(root/'input.npz',root/'chunks'/f'chunk_{i:04}.npz',i,3,trials=5)
            counts,means,cov=aggregate(root/'chunks',root/'results',plot=False)
            self.assertTrue((root/'results'/'summary.csv').exists())
            self.assertEqual(cov.shape,(4,4))
            self.assertTrue(np.all(np.isfinite(means)))
            self.assertGreater(counts.sum(),0)

    def test_reject_missing_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);xy,value=make_catalog(40)
            np.savez(root/'input.npz',xy=xy,value=value)
            process(root/'input.npz',root/'chunks'/'chunk_0000.npz',0,2,trials=3)
            with self.assertRaisesRegex(ValueError,'missing'):
                aggregate(root/'chunks',root/'results',plot=False)

if __name__=='__main__':unittest.main()
