#!/usr/bin/env python3
"""
MPV pipeline for the ThumbStack/TS filter outputs.

This script does both stages of the MPV workflow:
  1. chunk   : compute one catalog chunk contribution to the MPV estimator
  2. combine : combine chunk files into the final MPV curve, and optionally
               combine shuffled realizations into a covariance matrix

Important names:

  chunk-id   = which slice of the surviving catalog this job processes
  shuffle-id = which random shuffled/null realization this job belongs to

The script automatically loads the TS survivor mask and computes N_survive.
Extra SLURM array tasks beyond N_survive exit cleanly.

Directory layout:

  outdir/
      main/
          chunk_0000.npz
          chunk_0001.npz
          ...
      shuffles/
          shuffle_0000/
              chunk_0000.npz
              chunk_0001.npz
              ...
          shuffle_0001/
              chunk_0000.npz
              ...
      combined/
          MPV_true.npz
          MPV_shuffles_with_cov.npz

Example true chunk:

  python pipelines/mpv_pipeline.py chunk \
      --ts-dir /path/to/ts__map_example_map__cat_example_catalog \
      --outdir /path/to/mpv__map_example_map__cat_example_catalog \
      --chunk-id 0 \
      --chunk-size 100000

Example shuffled chunk:

  python pipelines/mpv_pipeline.py chunk \
      --shuffle \
      --shuffle-id 37 \
      --ts-dir /path/to/ts__map_example_map__cat_example_catalog \
      --outdir /path/to/mpv__map_example_map__cat_example_catalog \
      --chunk-id 0 \
      --chunk-size 100000

Example combine:

  python pipelines/mpv_pipeline.py combine --outdir /path/to/mpv__map_example_map__cat_example_catalog
  python pipelines/mpv_pipeline.py combine --shuffle --outdir /path/to/mpv__map_example_map__cat_example_catalog

"""

from __future__ import annotations
import argparse
import gc
import glob
import os
import re
import sys
import time as pytime
from dataclasses import dataclass
from pathlib import Path
import numpy as np


# Expected repository layout:
#
#   moving-lens-analysis-pipeline/
#       pipelines/
#           ts_pipeline.py
#           mpv_pipeline.py
#       outputs/
#

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Optional ThumbStack checkout used by the filtering/catalog path.
DEFAULT_THUMBSTACK_DIR = os.environ.get("THUMBSTACK_ROOT", "")

DEFAULT_CATALOG_NAME = "example_catalog"
DEFAULT_MAP_TAG = "unknownmap"

# If --outdir is omitted in chunk mode, the script derives it from --ts-dir:
#   outputs/ts__map_example_map__cat_example_catalog
# -> outputs/mpv__map_example_map__cat_example_catalog
DEFAULT_OUTPUT_PARENT = os.path.join(REPO_ROOT, "outputs")

# multiplicative factors to convert TS theta/phi filter outputs into velocity units.
# Default scale factors are unity; supply calibrated factors explicitly when needed.
DEFAULT_VPH_SCALE = 1.0
DEFAULT_VTH_SCALE = 1.0


def rss_gb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1e9
    except Exception:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6


def log(msg: str) -> None:
    print(msg, flush=True)


def mkdir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def safe_divide(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out = np.zeros_like(num, dtype=np.float64)
    good = den != 0
    out[good] = num[good] / den[good]
    return out


def parse_bins(args: argparse.Namespace) -> np.ndarray:
    if args.bins is not None:
        bins = np.array([float(x) for x in args.bins.split(",")], dtype=np.float64)
    else:
        bins = np.arange(args.bin_start, args.bin_stop, args.bin_step, dtype=np.float64)

    if bins.ndim != 1 or bins.size < 1:
        raise ValueError("bins must be a non-empty 1D array")
    if not np.all(np.diff(bins) > 0):
        raise ValueError(f"bins must be strictly increasing, got {bins}")
    return bins


def default_ts_paths(ts_dir: str, theta_name: str, phi_name: str) -> tuple[str, str, str]:
    """Return default theta, phi, and mask paths from a TS pipeline output folder.

    The TS pipeline writes compact names inside a descriptive directory, e.g.

      ts__map_example_map__cat_example_catalog/
          metadata.npz
          thumbstack_masks.npz
          thetamatched.npy
          phimatched.npy
    """
    ts = Path(ts_dir)
    theta = ts / f"{theta_name}.npy"
    phi = ts / f"{phi_name}.npy"
    mask = ts / "thumbstack_masks.npz"
    return str(theta), str(phi), str(mask)


def derive_mpv_outdir_from_ts_dir(ts_dir: str) -> str:
    """Derive a default MPV output directory from a TS output directory.

    Example:
      outputs/ts__map_example_map__cat_example_catalog
    becomes:
      outputs/mpv__map_example_map__cat_example_catalog

    If the TS directory does not follow the expected naming convention, fall
    back to outputs/mpv_outputs.
    """
    ts_path = Path(ts_dir).resolve()
    name = ts_path.name
    parent = ts_path.parent

    if name.startswith("ts__"):
        return str(parent / ("mpv__" + name[len("ts__") :]))

    return str(Path(DEFAULT_OUTPUT_PARENT) / "mpv_outputs")


def maybe_read_catalog_name_from_metadata(ts_dir: str, fallback: str) -> str:
    """Read catalog_name from metadata.npz when available; otherwise use fallback."""
    meta = Path(ts_dir) / "metadata.npz"
    if not meta.exists():
        return fallback
    try:
        d = np.load(meta, allow_pickle=True)
        if "catalog_name" in d:
            val = d["catalog_name"]
            if np.ndim(val) == 0:
                return str(val.item())
            return str(val)
    except Exception as exc:
        log(f"[warn] Could not read catalog_name from {meta}: {exc!r}; using {fallback}")
    return fallback


# ThumbStack catalog loading
def setup_thumbstack(thumbstack_dir: str):
    """Import external ThumbStack catalog machinery only when requested."""
    if not thumbstack_dir:
        raise ValueError(
            "No ThumbStack checkout configured. Supply --thumbstack-dir, set "
            "THUMBSTACK_ROOT, or use --catalog-npz with a catalog file."
        )
    thumbstack_dir = os.path.abspath(os.path.expanduser(thumbstack_dir))
    if not os.path.isdir(thumbstack_dir):
        raise FileNotFoundError(f"ThumbStack directory not found: {thumbstack_dir}")
    os.chdir(thumbstack_dir)
    if thumbstack_dir not in sys.path:
        sys.path.insert(0, thumbstack_dir)
    from catalog import Catalog  # type: ignore
    from driver_catalogs import massConversion, u  # type: ignore
    return Catalog, u, massConversion


def _read_catalog_npz(path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read a catalog file containing sky position and redshift.

    Accepted key sets are either:
      ra_deg, dec_deg, redshift
    or the common research-style aliases:
      RA, DEC, Z
    """
    data = np.load(path, allow_pickle=False)
    key_sets = [
        ("ra_deg", "dec_deg", "redshift"),
        ("RA", "DEC", "Z"),
    ]
    for ra_key, dec_key, z_key in key_sets:
        if all(k in data for k in (ra_key, dec_key, z_key)):
            ra = np.asarray(data[ra_key], dtype=np.float64).ravel()
            dec = np.asarray(data[dec_key], dtype=np.float64).ravel()
            redshift = np.asarray(data[z_key], dtype=np.float64).ravel()
            if not (ra.size == dec.size == redshift.size):
                raise ValueError(
                    f"Catalog arrays have inconsistent lengths: "
                    f"ra={ra.size}, dec={dec.size}, z={redshift.size}"
                )
            return ra, dec, redshift
    raise KeyError(
        f"Catalog file {path} must contain either "
        "(ra_deg, dec_deg, redshift) or (RA, DEC, Z)."
    )


def load_catalog_arrays(args: argparse.Namespace, idx_keep: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    """Load catalog coordinates from a portable NPZ file or external ThumbStack."""
    if args.catalog_npz:
        catalog_path = os.path.abspath(os.path.expanduser(args.catalog_npz))
        if not os.path.isfile(catalog_path):
            raise FileNotFoundError(f"Catalog NPZ not found: {catalog_path}")
        ra_all, dec_all, z_all = _read_catalog_npz(catalog_path)
        if idx_keep.max() >= ra_all.size:
            raise ValueError(
                f"Survivor index {idx_keep.max()} exceeds catalog length {ra_all.size}."
            )
        return ra_all[idx_keep], dec_all[idx_keep], z_all[idx_keep], catalog_path

    log("[diag] Loading catalog through external ThumbStack...")
    Catalog, u, massConversion = setup_thumbstack(args.thumbstack_dir)
    catal = Catalog(u, massConversion, name=args.catalog_name, nameLong=args.catalog_name, save=False)
    if idx_keep.max() >= len(catal.RA):
        raise ValueError(
            f"Survivor index {idx_keep.max()} exceeds ThumbStack catalog length {len(catal.RA)}."
        )
    return (
        np.asarray(catal.RA[idx_keep], dtype=np.float64),
        np.asarray(catal.DEC[idx_keep], dtype=np.float64),
        np.asarray(catal.Z[idx_keep], dtype=np.float64),
        f"thumbstack:{args.catalog_name}",
    )


# Cosmology / coordinate conversion
@dataclass
class ChiOfZ:
    za: np.ndarray
    chia: np.ndarray

    @classmethod
    def make(
        cls,
        omegab: float = 0.049,
        omegac: float = 0.261,
        h: float = 0.68,
        z1: float = 0.0,
        z2: float = 6.0,
        nz: int = 100000,
    ) -> "ChiOfZ":
        c_kms = 3e5
        omegam = omegab + omegac
        H0 = 100.0 * h
        za = np.linspace(z1, z2, nz)
        dz = za[1] - za[0]
        H = H0 * np.sqrt(omegam * (1.0 + za) ** 3 + 1.0 - omegam)
        chia = np.cumsum(c_kms / H) * dz
        return cls(za=za, chia=chia)

    def __call__(self, z: np.ndarray) -> np.ndarray:
        # Import scipy lazily so `combine` mode does not require scipy.
        from scipy.interpolate import interp1d
        return interp1d(self.za, self.chia, kind="cubic", fill_value="extrapolate")(z)


def convert_velocity_sph2cart(
    th: np.ndarray,
    ph: np.ndarray,
    v_r: np.ndarray,
    v_th: np.ndarray,
    v_ph: np.ndarray,
) -> np.ndarray:
    """Convert spherical velocity components to Cartesian coordinates."""
    row1 = np.stack((np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)))
    row2 = np.stack((np.cos(th) * np.cos(ph), np.cos(th) * np.sin(ph), -np.sin(th)))
    row3 = np.stack((-np.sin(ph), np.cos(ph), 0.0 * np.cos(th)))
    J = np.stack((row1, row2, row3))
    vij_sph = np.array([v_r, v_th, v_ph])
    vij_cart = np.einsum("ij...,i...->j...", J, vij_sph)
    return np.column_stack((vij_cart[0], vij_cart[1], vij_cart[2]))


def catalog_to_cartesian(
    ra_deg: np.ndarray,
    dec_deg: np.ndarray,
    redshift: np.ndarray,
    chi_of_z: ChiOfZ,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = chi_of_z(redshift)
    ra = np.radians(ra_deg)
    dec = np.radians(dec_deg)

    x = d * np.cos(dec) * np.cos(ra)
    y = d * np.cos(dec) * np.sin(ra)
    z = d * np.sin(dec)
    pos = np.vstack((x, y, z)).T

    th = np.pi / 2.0 - dec
    ph = ra
    return pos, th, ph


def _mask_key(masks: np.lib.npyio.NpzFile, kind: str, filter_name: str) -> str:
    """Return a mask key such as mask_post_outlier_thetamatched with helpful errors."""
    key = f"mask_{kind}_{filter_name}"
    if key in masks:
        return key

    matches = [k for k in masks.files if k.startswith(f"mask_{kind}_")]
    raise KeyError(
        f"Could not find {key!r} in thumbstack_masks.npz. "
        f"Available mask_{kind}_* keys are: {matches}"
    )


def load_survivor_indices(
    mask_path: str,
    theta_filter_name: str,
    phi_filter_name: str,
    mask_mode: str = "intersection",
) -> np.ndarray:
    """
    Load the TS post-outlier masks and return idx_keep.

    The TS pipeline saves keys named by filter output, e.g.
      mask_post_outlier_thetamatched
      mask_post_outlier_phimatched

    mask_mode:
      intersection : keep_phi & keep_theta  [recommended/current default]
      phi          : keep_phi only
      theta        : keep_theta only
      overlap      : overlap mask only
      all          : keep all objects with the length of the post-outlier masks
    """
    m = np.load(mask_path, allow_pickle=True)

    theta_key = _mask_key(m, "post_outlier", theta_filter_name)
    phi_key = _mask_key(m, "post_outlier", phi_filter_name)

    keep_theta = m[theta_key].astype(bool)
    keep_phi = m[phi_key].astype(bool)

    if keep_phi.shape != keep_theta.shape:
        raise ValueError(f"phi/theta mask shape mismatch: {keep_phi.shape} vs {keep_theta.shape}")

    if mask_mode == "intersection":
        keep = keep_phi & keep_theta
    elif mask_mode == "phi":
        keep = keep_phi
    elif mask_mode == "theta":
        keep = keep_theta
    elif mask_mode == "overlap":
        if "mask_overlap" not in m:
            raise KeyError("mask_mode='overlap' requested, but 'mask_overlap' is not in thumbstack_masks.npz")
        keep = m["mask_overlap"].astype(bool)
    elif mask_mode == "all":
        keep = np.ones_like(keep_phi, dtype=bool)
    else:
        raise ValueError(f"Unknown mask_mode={mask_mode}")

    log(
        "[diag] mask fractions: "
        f"phi({phi_filter_name})={keep_phi.mean():.6f} "
        f"theta({theta_filter_name})={keep_theta.mean():.6f} "
        f"selected={keep.mean():.6f} N_keep={int(keep.sum())}"
    )

    idx_keep = np.flatnonzero(keep)
    if idx_keep.size == 0:
        raise RuntimeError("No objects survived the selected TS mask.")
    return idx_keep

def compute_chunk_bounds(
    n_survive: int,
    chunk_id: int | None,
    chunk_size: int | None,
    n_chunks: int | None,
    i_start: int | None,
    i_end: int | None,
) -> tuple[int, int, str]:
    """
    Support three styles:
      1. manual: --i-start/--i-end
      2. fixed chunk size: --chunk-id/--chunk-size
      3. fixed number of chunks: --chunk-id/--n-chunks
    """
    if i_start is not None or i_end is not None:
        if i_start is None:
            i_start = 0
        if i_end is None or i_end < 0:
            i_end = n_survive
        return int(i_start), min(int(i_end), n_survive), f"manual_{int(i_start):07d}_{min(int(i_end), n_survive):07d}"

    if chunk_id is None:
        raise ValueError("chunk mode needs either --chunk-id or --i-start/--i-end")

    if chunk_size is not None and n_chunks is not None:
        raise ValueError("Use only one of --chunk-size or --n-chunks, not both.")

    if chunk_size is not None:
        i0 = int(chunk_id) * int(chunk_size)
        i1 = min((int(chunk_id) + 1) * int(chunk_size), n_survive)
        return i0, i1, f"chunk_{int(chunk_id):04d}"

    if n_chunks is not None:
        if chunk_id < 0 or chunk_id >= n_chunks:
            # This is intentionally safe for over-large arrays.
            return n_survive, n_survive, f"chunk_{int(chunk_id):04d}"
        edges = np.linspace(0, n_survive, int(n_chunks) + 1, dtype=int)
        i0 = int(edges[int(chunk_id)])
        i1 = int(edges[int(chunk_id) + 1])
        return i0, i1, f"chunk_{int(chunk_id):04d}"

    raise ValueError("Need one of --chunk-size, --n-chunks, or --i-start/--i-end.")


def load_filtered_velocities(
    theta_path: str,
    phi_path: str,
    idx_keep: np.ndarray,
    shuffle: bool,
    shuffle_id: int | None,
    seed_offset: int,
    vth_scale: float,
    vph_scale: float,
) -> tuple[np.ndarray, np.ndarray]:
    log("[diag] Loading TS theta/phi outputs with mmap...")
    vth_all = np.load(theta_path, mmap_mode="r")
    vph_all = np.load(phi_path, mmap_mode="r")

    if vth_all.shape[0] <= idx_keep.max() or vph_all.shape[0] <= idx_keep.max():
        raise ValueError(
            f"idx_keep max {idx_keep.max()} incompatible with theta {vth_all.shape} / phi {vph_all.shape}"
        )

    vth = np.asarray(vth_all[idx_keep, ...]).ravel()
    vph = np.asarray(vph_all[idx_keep, ...]).ravel()

    if shuffle:
        if shuffle_id is None:
            raise ValueError("--shuffle requires --shuffle-id")
        log(f"[diag] Applying velocity shuffle: shuffle_id={shuffle_id} seed={seed_offset + shuffle_id}")
        rng = np.random.default_rng(seed_offset + shuffle_id)
        perm = rng.permutation(vth.shape[0])
        vth = vth[perm]
        vph = vph[perm]

    vth = vth * vth_scale
    vph = vph * vph_scale

    del vth_all, vph_all
    gc.collect()
    log(f"[diag] Loaded velocities: vth={vth.shape} vph={vph.shape} RSS={rss_gb():.3f} GB")
    return vth, vph


def compute_mpv_chunk(
    pos: np.ndarray,
    trans_v_cart: np.ndarray,
    bins: np.ndarray,
    i_start: int,
    i_end: int,
    progress_step: int = 100000,
) -> tuple[np.ndarray, np.ndarray, np.int64]:
    """
    Stream over primary index i in [i_start, i_end) and accumulate
      num[b] = sum_ij Delta v_ij . q_ij
      den[b] = sum_ij q_ij . q_ij

    This keeps the chunk-combine math exact: full MPV = sum(num_chunks)/sum(den_chunks).
    """
    # Import scipy lazily so `combine` mode does not require scipy.
    from scipy.spatial import cKDTree

    t0 = pytime.time()
    tree = cKDTree(pos)
    max_bin = bins[-1]
    nbins = len(bins)

    num = np.zeros(nbins, dtype=np.float64)
    den = np.zeros(nbins, dtype=np.float64)

    # Preserve the estimator binning convention used by the research pipeline.
    edges = bins - bins[1] + bins[0] if len(bins) > 1 else np.array([0.0])

    norm_pos = np.sqrt((pos**2).sum(axis=1))
    pos_hats = pos / norm_pos[:, None]

    pair_count = np.int64(0)
    log(
        f"[diag] Streaming neighbor queries: N={pos.shape[0]} "
        f"i=[{i_start},{i_end}) max_bin={max_bin} RSS={rss_gb():.3f} GB"
    )

    for i in range(i_start, i_end):
        neigh = tree.query_ball_point(pos[i], max_bin)

        for j in neigh:
            if j <= i:
                continue

            rel_pos = pos[i] - pos[j]
            rel_vel = trans_v_cart[i] - trans_v_cart[j]
            mag = np.sqrt(rel_pos[0] ** 2 + rel_pos[1] ** 2 + rel_pos[2] ** 2)
            if mag == 0:
                continue

            b = np.digitize(mag, edges) - 1
            if b < 0 or b >= nbins:
                continue

            pos_hat_ij = rel_pos / mag
            dot_i = np.dot(pos_hat_ij, pos_hats[i])
            dot_j = np.dot(pos_hat_ij, pos_hats[j])
            q = pos_hat_ij - 0.5 * (dot_i * pos_hats[i] + dot_j * pos_hats[j])

            num[b] += np.dot(rel_vel, q)
            den[b] += np.dot(q, q)
            pair_count += 1

        if progress_step > 0 and (i - i_start) > 0 and (i - i_start) % progress_step == 0:
            log(
                f"[diag] i={i} pairs={pair_count} RSS={rss_gb():.3f} GB "
                f"elapsed_min={(pytime.time() - t0) / 60:.2f}"
            )
            gc.collect()

    log(
        f"[diag] DONE chunk: total_pairs={pair_count} RSS={rss_gb():.3f} GB "
        f"total_min={(pytime.time() - t0) / 60:.2f}"
    )
    return num, den, np.int64(pair_count)



def run_chunk(args: argparse.Namespace) -> None:
    bins = parse_bins(args)

    if args.outdir is None:
        args.outdir = derive_mpv_outdir_from_ts_dir(args.ts_dir)
        log(f"[diag] --outdir not supplied; using derived output directory: {args.outdir}")

    args.catalog_name = maybe_read_catalog_name_from_metadata(args.ts_dir, args.catalog_name)
    theta_path, phi_path, mask_path = default_ts_paths(
        args.ts_dir, args.theta_filter_name, args.phi_filter_name
    )
    theta_path = args.theta_path or theta_path
    phi_path = args.phi_path or phi_path
    mask_path = args.mask_path or mask_path

    for label, path in [("theta", theta_path), ("phi", phi_path), ("mask", mask_path)]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {label} file: {path}")

    log(f"[diag] PID={os.getpid()} RSS={rss_gb():.3f} GB start")
    log(f"[diag] theta_path={theta_path}")
    log(f"[diag] phi_path={phi_path}")
    log(f"[diag] mask_path={mask_path}")

    idx_keep = load_survivor_indices(
        mask_path,
        theta_filter_name=args.theta_filter_name,
        phi_filter_name=args.phi_filter_name,
        mask_mode=args.mask_mode,
    )
    n_survive = int(idx_keep.size)

    i_start, i_end, chunk_tag = compute_chunk_bounds(
        n_survive=n_survive,
        chunk_id=args.chunk_id,
        chunk_size=args.chunk_size,
        n_chunks=args.n_chunks,
        i_start=args.i_start,
        i_end=args.i_end,
    )

    if i_start >= n_survive or i_start >= i_end:
        log(
            f"[diag] chunk_id={args.chunk_id} is beyond N_survive={n_survive}. "
            "Exiting cleanly without writing a chunk file."
        )
        return

    log(f"[diag] N_survive={n_survive} chunk_tag={chunk_tag} i=[{i_start},{i_end})")

    vth, vph = load_filtered_velocities(
        theta_path=theta_path,
        phi_path=phi_path,
        idx_keep=idx_keep,
        shuffle=args.shuffle,
        shuffle_id=args.shuffle_id,
        seed_offset=args.seed_offset,
        vth_scale=args.vth_scale,
        vph_scale=args.vph_scale,
    )

    if vth.size != n_survive or vph.size != n_survive:
        raise ValueError(f"Velocity sizes do not match N_survive: {vth.size}, {vph.size}, {n_survive}")

    ra, dec, redshift, catalog_source = load_catalog_arrays(args, idx_keep)

    if not (ra.size == dec.size == redshift.size == vth.size == vph.size):
        raise ValueError(
            f"Shape mismatch: ra={ra.size} dec={dec.size} z={redshift.size} vth={vth.size} vph={vph.size}"
        )

    log(f"[diag] Catalog loaded/sliced: N={ra.size} RSS={rss_gb():.3f} GB")

    chi_of_z = ChiOfZ.make(nz=args.nz_chi)
    pos, th, ph = catalog_to_cartesian(ra, dec, redshift, chi_of_z)
    vr = np.zeros_like(vph)
    trans_v_cart = convert_velocity_sph2cart(th, ph, vr, vth, vph)
    log(f"[diag] Coordinate/velocity conversion done RSS={rss_gb():.3f} GB")

    num, den, pair_count = compute_mpv_chunk(
        pos=pos,
        trans_v_cart=trans_v_cart,
        bins=bins,
        i_start=i_start,
        i_end=i_end,
        progress_step=args.progress_step,
    )

    if args.shuffle:
        if args.shuffle_id is None:
            raise ValueError("--shuffle requires --shuffle-id")
        chunk_dir = Path(args.outdir) / "shuffles" / f"shuffle_{args.shuffle_id:04d}"
    else:
        chunk_dir = Path(args.outdir) / "main"
    mkdir(chunk_dir)

    if args.chunk_id is not None:
        out_path = chunk_dir / f"chunk_{args.chunk_id:04d}.npz"
    else:
        # Manual i-start/i-end fallback.
        out_path = chunk_dir / f"chunk_{chunk_tag}.npz"

    mpv_chunk = safe_divide(num, den)
    np.savez(
        out_path,
        num=num,
        den=den,
        mpv_chunk=mpv_chunk,
        pair_count=np.int64(pair_count),
        bins=bins,
        n_survive=np.int64(n_survive),
        i_start=np.int64(i_start),
        i_end=np.int64(i_end),
        chunk_id=np.int64(args.chunk_id if args.chunk_id is not None else -1),
        shuffle=np.bool_(args.shuffle),
        shuffle_id=np.int64(args.shuffle_id if args.shuffle_id is not None else -1),
        theta_path=theta_path,
        phi_path=phi_path,
        mask_path=mask_path,
        catalog_name=args.catalog_name,
        catalog_source=catalog_source,
        map_tag=args.map_tag,
    )

    log(f"[diag] Saved chunk -> {out_path}")
    log(f"[diag] mpv_chunk = {mpv_chunk}")
    log(f"[diag] DONE RSS={rss_gb():.3f} GB")



def load_and_sum_chunks(files: list[str]) -> dict[str, object]:
    if not files:
        raise RuntimeError("No chunk files supplied to load_and_sum_chunks.")

    num_tot = None
    den_tot = None
    pairs_tot = np.int64(0)
    starts: list[int] = []
    ends: list[int] = []
    chunk_ids: list[int] = []
    bins = None
    n_survive_values: list[int] = []

    for k, f in enumerate(files):
        d = np.load(f, allow_pickle=True)
        num = d["num"].astype(np.float64, copy=False)
        den = d["den"].astype(np.float64, copy=False)
        pc = np.int64(d["pair_count"])

        if num_tot is None:
            num_tot = np.zeros_like(num, dtype=np.float64)
            den_tot = np.zeros_like(den, dtype=np.float64)
            bins = d["bins"].astype(np.float64, copy=False) if "bins" in d else None

        if num.shape != num_tot.shape or den.shape != den_tot.shape:
            raise ValueError(f"Shape mismatch in {f}: num={num.shape} den={den.shape} expected={num_tot.shape}")

        num_tot += num
        den_tot += den
        pairs_tot += pc

        if "i_start" in d:
            starts.append(int(d["i_start"]))
        if "i_end" in d:
            ends.append(int(d["i_end"]))
        if "chunk_id" in d:
            chunk_ids.append(int(d["chunk_id"]))
        if "n_survive" in d:
            n_survive_values.append(int(d["n_survive"]))

        if (k + 1) % 10 == 0 or (k + 1) == len(files):
            log(f"[combine] {k + 1}/{len(files)} chunks; pairs_tot={pairs_tot}")

    assert num_tot is not None and den_tot is not None
    mpv = safe_divide(num_tot, den_tot)

    return {
        "mpv": mpv,
        "num_tot": num_tot,
        "den_tot": den_tot,
        "pair_count_tot": pairs_tot,
        "bins": bins,
        "n_chunks": len(files),
        "i_start_min": min(starts) if starts else -1,
        "i_end_max": max(ends) if ends else -1,
        "chunk_ids": np.array(chunk_ids, dtype=np.int64),
        "n_survive": np.int64(n_survive_values[0]) if n_survive_values else np.int64(-1),
        "den_zero_bins": np.where(den_tot == 0)[0].astype(np.int64),
    }


def warn_about_chunk_coverage(chunk_ids: np.ndarray, label: str) -> None:
    if chunk_ids.size == 0 or np.any(chunk_ids < 0):
        return
    unique = np.unique(chunk_ids)
    expected = np.arange(unique.min(), unique.max() + 1)
    missing = np.setdiff1d(expected, unique)
    if missing.size:
        log(f"[warn] {label}: missing chunk ids between min/max: {missing}")


def combine_true(args: argparse.Namespace) -> None:
    main_dir = Path(args.outdir) / "main"
    files = sorted(glob.glob(str(main_dir / "chunk_*.npz")))
    if not files:
        raise RuntimeError(f"No chunk_*.npz files found in {main_dir}")

    log(f"[combine] Combining true chunks from {main_dir}; n_files={len(files)}")
    result = load_and_sum_chunks(files)
    warn_about_chunk_coverage(result["chunk_ids"], "true")

    combined_dir = Path(args.outdir) / "combined"
    mkdir(combined_dir)
    out_path = combined_dir / "MPV_true.npz"

    np.savez(
        out_path,
        mpv=result["mpv"],
        num_tot=result["num_tot"],
        den_tot=result["den_tot"],
        pair_count_tot=np.int64(result["pair_count_tot"]),
        bins=result["bins"],
        n_chunks=np.int64(result["n_chunks"]),
        n_survive=np.int64(result["n_survive"]),
        i_start_min=np.int64(result["i_start_min"]),
        i_end_max=np.int64(result["i_end_max"]),
        chunk_ids=result["chunk_ids"],
        den_zero_bins=result["den_zero_bins"],
    )

    log(f"[combine] Saved true MPV -> {out_path}")
    log(f"[combine] MPV = {result['mpv']}")
    log(f"[combine] den==0 bins = {result['den_zero_bins']}")


def shuffle_id_from_dir(path: str) -> int | None:
    m = re.search(r"shuffle_(\d+)$", os.path.basename(path.rstrip("/")))
    return int(m.group(1)) if m else None


def combine_shuffles(args: argparse.Namespace) -> None:
    shuff_base = Path(args.outdir) / "shuffles"
    shuff_dirs = sorted(glob.glob(str(shuff_base / "shuffle_*")))
    shuff_dirs = [d for d in shuff_dirs if os.path.isdir(d)]
    if not shuff_dirs:
        raise RuntimeError(f"No shuffle_* directories found in {shuff_base}")

    combined_dir = Path(args.outdir) / "combined"
    per_shuffle_dir = combined_dir / "per_shuffle"
    mkdir(combined_dir)
    mkdir(per_shuffle_dir)

    all_shuffle_ids: list[int] = []
    all_mpv: list[np.ndarray] = []
    all_n_chunks: list[int] = []

    for sdir in shuff_dirs:
        sid = shuffle_id_from_dir(sdir)
        if sid is None:
            log(f"[skip] Could not parse shuffle id from {sdir}")
            continue

        files = sorted(glob.glob(os.path.join(sdir, "chunk_*.npz")))
        if not files:
            log(f"[skip] No chunk files in {sdir}")
            continue

        result = load_and_sum_chunks(files)
        warn_about_chunk_coverage(result["chunk_ids"], f"shuffle_{sid:04d}")

        if args.require_nchunks is not None and int(result["n_chunks"]) != args.require_nchunks:
            log(
                f"[skip] shuffle_{sid:04d} has {result['n_chunks']} chunks; "
                f"required {args.require_nchunks}"
            )
            continue

        out_one = per_shuffle_dir / f"MPV_shuffle_{sid:04d}.npz"
        np.savez(
            out_one,
            shuffle_id=np.int64(sid),
            mpv=result["mpv"],
            num_tot=result["num_tot"],
            den_tot=result["den_tot"],
            pair_count_tot=np.int64(result["pair_count_tot"]),
            bins=result["bins"],
            n_chunks=np.int64(result["n_chunks"]),
            n_survive=np.int64(result["n_survive"]),
            chunk_ids=result["chunk_ids"],
            den_zero_bins=result["den_zero_bins"],
        )
        log(f"[shuffle] Saved combined shuffle -> {out_one}")

        all_shuffle_ids.append(sid)
        all_mpv.append(result["mpv"])
        all_n_chunks.append(int(result["n_chunks"]))

    if not all_mpv:
        raise RuntimeError("No shuffled realizations were successfully combined.")

    order = np.argsort(all_shuffle_ids)
    shuffle_ids = np.array(all_shuffle_ids, dtype=np.int64)[order]
    mpv_all = np.stack(all_mpv, axis=0)[order]
    n_chunks_per_shuffle = np.array(all_n_chunks, dtype=np.int64)[order]

    mean_mpv = mpv_all.mean(axis=0)
    if mpv_all.shape[0] >= 2:
        cov = np.cov(mpv_all, rowvar=False, ddof=1)
        err = np.sqrt(np.diag(cov))
        with np.errstate(divide="ignore", invalid="ignore"):
            corr = cov / np.outer(err, err)
    else:
        cov = np.full((mpv_all.shape[1], mpv_all.shape[1]), np.nan)
        err = np.full(mpv_all.shape[1], np.nan)
        corr = np.full_like(cov, np.nan)
        log("[warn] Only one shuffled realization; covariance is undefined and saved as NaN.")

    bins = parse_bins(args)
    master_out = combined_dir / "MPV_shuffles_with_cov.npz"
    np.savez(
        master_out,
        shuffle_ids=shuffle_ids,
        mpv_all=mpv_all,
        mean_mpv=mean_mpv,
        cov=cov,
        err=err,
        corr=corr,
        bins=bins,
        n_shuffles=np.int64(mpv_all.shape[0]),
        n_bins=np.int64(mpv_all.shape[1]),
        n_chunks_per_shuffle=n_chunks_per_shuffle,
    )

    log(f"[master] Saved shuffled ensemble/cov -> {master_out}")
    log(f"[master] mpv_all shape = {mpv_all.shape}")
    log(f"[master] n_shuffles = {mpv_all.shape[0]}")


def run_combine(args: argparse.Namespace) -> None:
    if args.outdir is None:
        raise ValueError("combine mode requires --outdir, e.g. --outdir outputs/mpv__map_<map>__cat_<catalog>")
    if args.shuffle:
        combine_shuffles(args)
    else:
        combine_true(args)


def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--outdir",
        default=None,
        help=(
            "MPV output directory. In chunk mode, if omitted, this is derived from --ts-dir "
            "by replacing the leading 'ts__' folder prefix with 'mpv__'. In combine mode, "
            "--outdir is required."
        ),
    )
    p.add_argument("--bins", default=None, help="Comma-separated bin labels, e.g. '10,20,30'. Overrides bin-start/stop/step.")
    p.add_argument("--bin-start", type=float, default=10.0)
    p.add_argument("--bin-stop", type=float, default=180.0)
    p.add_argument("--bin-step", type=float, default=10.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chunked MPV pipeline for transverse-filter outputs")
    sub = parser.add_subparsers(dest="command", required=True)

    p_chunk = sub.add_parser("chunk", help="compute one MPV chunk")
    add_common_args(p_chunk)
    p_chunk.add_argument(
        "--thumbstack-dir",
        default=DEFAULT_THUMBSTACK_DIR,
        help=(
            "Path to a compatible external ThumbStack checkout. Optional when "
            "--catalog-npz is supplied; can also be set with THUMBSTACK_ROOT."
        ),
    )
    p_chunk.add_argument(
        "--catalog-npz",
        default=None,
        help=(
            "Portable catalog input containing ra_deg, dec_deg, redshift "
            "(or RA, DEC, Z). When provided, ThumbStack is not needed for the MPV stage."
        ),
    )
    p_chunk.add_argument(
        "--ts-dir",
        required=True,
        help="Path to a TS output directory, e.g. outputs/ts__map_<map>__cat_<catalog>.",
    )
    p_chunk.add_argument("--catalog-name", default=DEFAULT_CATALOG_NAME)
    p_chunk.add_argument("--map-tag", default=DEFAULT_MAP_TAG, help="Saved as metadata only; TS output filenames no longer need this.")
    p_chunk.add_argument("--theta-filter-name", default="thetamatched", help="Basename of theta TS output and mask suffix.")
    p_chunk.add_argument("--phi-filter-name", default="phimatched", help="Basename of phi TS output and mask suffix.")

    # Explicit paths override the default TS output convention.
    p_chunk.add_argument("--theta-path", default=None, help="Optional explicit path to theta .npy; default is TS_DIR/thetamatched.npy")
    p_chunk.add_argument("--phi-path", default=None, help="Optional explicit path to phi .npy; default is TS_DIR/phimatched.npy")
    p_chunk.add_argument("--mask-path", default=None, help="Optional explicit path to masks .npz; default is TS_DIR/thumbstack_masks.npz")

    p_chunk.add_argument("--mask-mode", choices=["intersection", "phi", "theta", "overlap", "all"], default="intersection")

    # Chunking modes.
    p_chunk.add_argument("--chunk-id", type=int, default=None, help="catalog chunk id for automatic chunking")
    p_chunk.add_argument("--chunk-size", type=int, default=None, help="objects per chunk; used with --chunk-id")
    p_chunk.add_argument("--n-chunks", type=int, default=None, help="total number of chunks; used with --chunk-id")
    p_chunk.add_argument("--i-start", type=int, default=None, help="manual start index in surviving catalog")
    p_chunk.add_argument("--i-end", type=int, default=None, help="manual end index in surviving catalog")

    # Shuffle/null controls.
    p_chunk.add_argument("--shuffle", action="store_true", help="shuffle theta/phi filtered velocities among galaxies")
    p_chunk.add_argument("--shuffle-id", type=int, default=None, help="which shuffled/null realization this chunk belongs to")
    p_chunk.add_argument("--seed-offset", type=int, default=12345)

    # Velocity scaling.
    p_chunk.add_argument("--vth-scale", type=float, default=DEFAULT_VTH_SCALE)
    p_chunk.add_argument("--vph-scale", type=float, default=DEFAULT_VPH_SCALE)

    p_chunk.add_argument("--nz-chi", type=int, default=100000)
    p_chunk.add_argument("--progress-step", type=int, default=100000)
    p_chunk.set_defaults(func=run_chunk)

    p_combine = sub.add_parser("combine", help="combine chunks into true MPV or shuffled covariance")
    add_common_args(p_combine)
    p_combine.add_argument("--shuffle", action="store_true", help="combine shuffled realizations and compute covariance")
    p_combine.add_argument(
        "--require-nchunks",
        type=int,
        default=None,
        help="Optional: require exactly this many chunks per shuffle; otherwise combine whatever exists.",
    )
    p_combine.set_defaults(func=run_combine)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
