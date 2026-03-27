# coding=utf-8

from dataclasses import dataclass

import numpy as np

from .aux_functions import convexHull
from .sps_io_and_qc import (deletePntDuplicates, deletePntOrphans,
                            deleteRelDuplicates, deleteRelOrphans,
                            getAliveAndDead)


@dataclass(frozen=True)
class PointFilterDerivedState:
    liveE: np.ndarray | None
    liveN: np.ndarray | None
    deadE: np.ndarray | None
    deadN: np.ndarray | None
    bound: np.ndarray | None = None


@dataclass(frozen=True)
class FilterResult:
    key: str
    array: np.ndarray | None
    before: int
    after: int
    message: str
    changed: bool
    refreshLayout: bool
    derivedState: PointFilterDerivedState | None = None


@dataclass(frozen=True)
class _FilterDefinition:
    messageSuffix: str
    kind: str
    recomputeBound: bool
    relationSourceMode: bool | None = None


class FilterService:
    _definitions = {
        'rps_duplicates': _FilterDefinition('rps-duplicates', 'point-duplicates', True),
        'sps_duplicates': _FilterDefinition('sps-duplicates', 'point-duplicates', True),
        'rps_orphans': _FilterDefinition('rps/xps-orphans', 'point-orphans', True),
        'sps_orphans': _FilterDefinition('sps/xps-orphans', 'point-orphans', True),
        'xps_duplicates': _FilterDefinition('xps-duplicates', 'relation-duplicates', False),
        'xps_sps_orphans': _FilterDefinition('xps/sps-orphans', 'relation-orphans', False, relationSourceMode=True),
        'xps_rps_orphans': _FilterDefinition('xps/rps-orphans', 'relation-orphans', False, relationSourceMode=False),
        'rec_duplicates': _FilterDefinition('rec-duplicates', 'point-duplicates', False),
        'src_duplicates': _FilterDefinition('src-duplicates', 'point-duplicates', False),
        'rec_orphans': _FilterDefinition('rec/rel-orphans', 'point-orphans', False),
        'src_orphans': _FilterDefinition('src/rel-orphans', 'point-orphans', False),
        'rel_duplicates': _FilterDefinition('rel-duplicates', 'relation-duplicates', False),
        'rel_src_orphans': _FilterDefinition('rel/src-orphans', 'relation-orphans', False, relationSourceMode=True),
        'rel_rec_orphans': _FilterDefinition('rel/rec-orphans', 'relation-orphans', False, relationSourceMode=False),
    }

    def applyFilter(self, filterKey, array):
        definition = self._definitions[filterKey]
        if array is None:
            return None

        if definition.kind == 'point-duplicates':
            filtered, before, after = deletePntDuplicates(array)
        elif definition.kind == 'point-orphans':
            filtered, before, after = deletePntOrphans(array)
        elif definition.kind == 'relation-duplicates':
            filtered, before, after = deleteRelDuplicates(array)
        elif definition.kind == 'relation-orphans':
            filtered, before, after = deleteRelOrphans(array, definition.relationSourceMode)
        else:
            raise ValueError(f'Unknown filter kind: {definition.kind}')

        changed = after < before
        derivedState = None
        refreshLayout = changed and definition.kind.startswith('point')
        if refreshLayout:
            liveE, liveN, deadE, deadN = getAliveAndDead(filtered)
            bound = convexHull(liveE, liveN) if definition.recomputeBound and liveE is not None and liveN is not None else None
            derivedState = PointFilterDerivedState(liveE=liveE, liveN=liveN, deadE=deadE, deadN=deadN, bound=bound)

        return FilterResult(
            key=filterKey,
            array=filtered,
            before=before,
            after=after,
            message=f'Filter : Filtered {before:,} records. Removed {(before - after):,} {definition.messageSuffix}',
            changed=changed,
            refreshLayout=refreshLayout,
            derivedState=derivedState,
        )
