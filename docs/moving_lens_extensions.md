# Moving-Lens Extensions

The moving-lens analysis augments the ThumbStack filtering workflow with directional matched filters and transverse-velocity signal templates.

## Directional filter family

The two local transverse components are measured with the following filters:

- `phimatched`
- `thetamatched`
- `phimatchedrot90`
- `thetamatchedrot90`
- `phimatchedNullGrad`
- `thetamatchedNullGrad`
- `phimatchedrot90NullGrad`
- `thetamatchedrot90NullGrad`

`extensions/moving_lens_filters.py` implements the filter kernels. Radial profiles are supplied as callable inputs, allowing the same filter machinery to be used with different signal models.

The rotated filters provide orthogonal null tests, while the gradient-null variants remove the leading response to a local linear gradient.

## Moving-lens dipole template

`extensions/moving_lens_template.py` evaluates the moving-lens temperature dipole associated with an object's transverse velocity and a radial deflection profile.

For transverse components \(v_\theta\) and \(v_\phi\), the template projects the velocity vector onto the local deflection direction and scales it by \(T_\mathrm{CMB}/c\).

## Pipeline integration

`pipelines/ts_pipeline.py` handles the filtering stage:

1. load the map, mask, and object catalog;
2. run the directional filter set;
3. apply selection and outlier masks;
4. save the per-object transverse filter measurements; and
5. pass those outputs to the MPV analysis.

`pipelines/mpv_pipeline.py` then computes the pairwise estimator in chunks and combines true and shuffled realizations into the final MPV and covariance products.
