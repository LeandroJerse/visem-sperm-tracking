"""Manual unit-testing sandbox for the detection baselines.

Run a single detector on a **single frame** and inspect every intermediate
stage (gray, binary mask, morphology, contours) plus the final detections, so
parameters can be tuned in isolation. See :mod:`tests.sandbox.single_frame`.
"""
