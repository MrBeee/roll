# Implementation of the Ramer-Douglas-Peucker algorithm for polylines using a point-to-line-segment distance measure.
#
# This is a copy of: https://github.com/avitase/rdppy/blob/main/src/rdppy/rdp.py
# using a local copy, rather than having to install this module and create another dependency
# See: https://github.com/avitase/rdppy/tree/main

from typing import Any, Callable, Optional

import numpy as np


def dist2(points, start, end):
    if np.allclose(start, end):
        return np.sum((points - start) ** 2, axis=1)

    d = np.divide(end - start, np.sqrt(np.sum((end - start) ** 2)))

    max_p1 = np.dot(start - points, d).max()
    max_p2 = np.dot(points - end, d).max()

    return max(max_p1, max_p2, 0) ** 2 + np.cross(points - np.expand_dims(start, 0), np.expand_dims(d, 0)) ** 2


def _filter(points, threshold, dist2_fun):
    if points.shape[0] <= 2:
        return np.array([True] * points.shape[0])

    start = points[0]
    end = points[-1]

    d = dist2_fun(points[1:-1], start, end)
    i = np.argmax(d) + 1
    d_max = d[i - 1]

    return (
        np.concatenate(
            [
                _filter(points[: i + 1], threshold, dist2_fun)[:-1],
                _filter(points[i:], threshold, dist2_fun),
            ]
        )
        if d_max > threshold**2
        else np.array(
            [True] + [False] * (points.shape[0] - 2) + [True],
        )
    )


def filterRdp(points: Any, threshold: float, dist2_fun: Optional[Callable] = None) -> Any:
    """Uses the Ramer-Douglas-Peucker algorithm to filter a given sequence w.r.t. a threshold value.

    Uses the Ramer-Douglas-Peucker algorithm to filter a given sequence of points w.r.t. a threshold
    value. Note that this function does not return a sequence of points but a binary mask which can
    be applied to the sequence to find the nodes of the simplified curve.

    :param points: A sequence of points.
    :param threshold: The threshold value (aka epsilon) of the Ramer-Douglas-Peucker algorithm.
    :return: Binary mask as numpy array of same length as input.
    """
    if len(points) == 0:
        return points

    points = np.array(points)

    if len(points.shape) != 2:
        raise ValueError('Points have to be a sequence of coordinate tuples, (e.g., [(x1, y1), (x2, y2), ...])')

    if points.shape[-1] != 2 and dist2_fun is None:
        raise ValueError('The default distance metric only works for sequences of 2D tuples.')

    return _filter(points, threshold, dist2_fun if dist2_fun is not None else dist2)
