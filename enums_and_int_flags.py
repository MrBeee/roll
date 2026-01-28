# enums_and_int_flags.py

from enum import Enum, IntFlag


class MsgType(Enum):
    Info = 0
    Binning = 1
    Geometry = 2
    Debug = 3
    Warning = 4
    Error = 5
    Exception = 6


class Direction(Enum):
    NA = 0
    Up = 1
    Dn = 2
    Lt = 3
    Rt = 4

class SeedType(IntFlag):
    rollingGrid = 0
    fixedGrid = 1
    circle = 2
    spiral = 3
    well = 4

class SurveyType(Enum):
    Orthogonal = 0
    Parallel = 1
    Slanted = 2
    Brick = 3
    Zigzag = 4
    Streamer = 5

class SurveyType2(Enum):
    Orthogonal = (0, "Orthogonal - standard manner of acquiring land data")
    Parallel   = (1, "Parallel - standard manner of acquiring OBN data")
    Slanted    = (2, "Slanted - legacy variation on orthogonal, aiming to reduce LMOS")
    Brick      = (3, "Brick - legacy variation on orthogonal, aiming to reduce LMOS")
    Zigzag     = (4, "zigzag - legacy manner acquiring narrrow azimuth vibroseis data")
    Streamer   = (5, "streamer - towed streamer marine survey")
    # Orthogonal = ("Orthogonal", "Orthogonal - standard manner of acquiring land data")
    # Parallel   = ("Parallel",   "Parallel - standard manner of acquiring OBN data")
    # Slanted    = ("Slanted",    "Slanted - legacy variation on orthogonal, aiming to reduce LMOS")
    # Brick      = ("Brick",      "Brick - legacy variation on orthogonal, aiming to reduce LMOS")
    # Zigzag     = ("Zigzag",     "zigzag - legacy manner acquiring narrrow azimuth vibroseis data")
    # Streamer   = ("Streamer",   "streamer - towed streamer marine survey")

    @property
    def code(self) -> int:
        return self.value[0]

    @property
    def description(self) -> str:
        return self.value[1]

    @classmethod
    def descriptions(cls) -> list[str]:
        return [m.description for m in cls]

    @classmethod
    def from_code(cls, code: int) -> "SurveyType2":
        return next(m for m in cls if m.code == code)

    @classmethod
    def names(cls) -> list[str]:
        return [m.name for m in cls]


class PaintMode(IntFlag):
    none = 0            # reset the whole lot
    justBlocks = 1      # just src, rec & cmp block outlines
    justTemplates = 2   # just template rect boundaries
    justLines = 3       # just lines
    justPoints = 4      # just points
    all = 5             # down to patterns


class PaintDetails(IntFlag):
    none = 0        # reset the whole lot

    # receiver details
    recPat = 1      # show rec patterns
    recPnt = 2      # show rec points
    recLin = 4      # show rec lines
    recAll = 7      # show all rec details

    # source details
    srcPat = 8      # show src patterns
    srcPnt = 16     # show src points
    srcLin = 32     # show src lines
    srcAll = 56     # show all source details

    # show all receiver and source details
    srcAndRec = 63  # show all src and rec details

    # show templates ... or not
    templat = 64    # complete templates

    # show relevant areas
    srcArea = 128   # just src area
    recArea = 256   # just rec area
    cmpArea = 512   # just cmp area

    # show all above listed areas
    allArea = 896  # show all areas

    all = 1023      # all bits defined sofar are set

    # note: clearing a flag works with flag &= ~flagToClear
