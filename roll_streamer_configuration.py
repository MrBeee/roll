import math

from . import config  # used to pass initial settings
from .aux_functions import (knotToMeterperSec, newtonToTonForce,
                            tonForceToNewton)


class RollStreamerConfiguration:
    # assign default name
    def __init__(self) -> None:
        self.noStreamers = 10                                                   # [int]
        self.noSources = 2                                                      # [int]
        self.vesselSpeed = 4.5                                                  # [knot]    default vessel speed

        self.streamerSeparationFront = 100.0                                    # [m]       streamer interval at start of spread
        self.streamerSeparationRear = 120.0                                     # [m]       streamer interval at end of spread

        self.streamerDepthFront = 8.0                                           # [m]       streamer depth
        self.streamerDepthAft = 10.0                                            # [m]       streamer depth at end of spread
        self.sourceDepth = 10.0                                                 # [m]       source depth default

        self.streamerLength = 6000.0                                            # [m]       default streamer length
        self.GroupInterval = 12.5                                               # [m]       default group interval
        self.sourcePopInterval = 12.5                                           # [m]       default pop-interval

        self.streamerDiameter = 0.06                                            # [m]       default streamer diameter
        self.dragCoefficient = 0.0055                                           # [n/a]

        self.minInnerStreamerSpeed = 3.8                                        # [knot]    relevant for inner streamer
        self.maxDragForce = 3.07                                                # ton-force] relevant for outer streamer

        self.crossCurrent = 0.0                                                 # [knot]    determines feather angle
        self.seawaterDensity = 1029.0                                           # [kg/m3]   influences drag per meter

        # calculated variables
        self.spreadWidth = None                                                 # [m]       (no streamers - 1) x streamer separation
        self.wetSurface = None                                                  # [m2]      pi x length x diameter
        self.dragPerMeter = None                                                # [kg/m]    0.5 x wet surface x density x drag coefficient

        self.innerTurningRadius = None                                          # [m]       minimum turning radius for inner streamer
        self.outerTurningRadius = None                                          # [m]       minimum turning radius for outer streamer
        self.vesselTurningRadius = None                                         # [m]       vessel turning radius. max(inner, outer)

        self.innerStreamerSpeed = None                                          # [m/s]     speed of inner streamer
        self.outerStreamerSpeed = None                                          # [m/s]     speed of outer streamer

        self.innerStreamerDrag = None                                           # [N]       combined drag x inner streamer speed
        self.outerStreamerDrag = None                                           # [N]       combined drag x outer streamer speed

        self.featherAngle = None                                                # [deg]     feather angle as a result of vessel speed and cross current
        self.effectiveSpeed = None                                              # [knot]    forward speed, corrected for cross currents & feather
        self.streamerLayback = None                                             # [m]       usually about half the spread width

    def initializeSpread(self):
        self.spreadWidth = (self.noStreamers - 1) * self.streamerSeparationFront
        self.streamerLayback = 0.5 * self.spreadWidth

        self.innerTurningRadius = 0.5 * self.vesselSpeed * self.spreadWidth / (self.vesselSpeed - self.minInnerStreamerSpeed)   # speed in knot or m/s does not matter for their ratio

        self.wetSurface = math.pi * self.streamerLength * self.streamerDiameter
        self.dragPerMeter = 0.5 * self.wetSurface * self.seawaterDensity * self.dragCoefficient

        self.innerStreamerSpeed = knotToMeterperSec(self.minInnerStreamerSpeed)   # [m/s]     speed of inner streamer
        self.outerStreamerSpeed = knotToMeterperSec(self.vesselSpeed) / self.innerTurningRadius * (self.innerTurningRadius + 0.5 * self.spreadWidth)  # [m/s]     speed of outer streamer

        self.innerStreamerDrag = newtonToTonForce(self.dragPerMeter * self.innerStreamerSpeed**2)
        self.outerStreamerDrag = newtonToTonForce(self.dragPerMeter * self.outerStreamerSpeed**2)

        a = 1.0 - tonForceToNewton(self.maxDragForce) / (self.dragPerMeter * knotToMeterperSec(self.vesselSpeed) ** 2.0)
        b = self.spreadWidth
        c = 0.25 * self.spreadWidth**2.0
        self.outerTurningRadius = (-1.0 * b - math.sqrt(b**2 - 4 * a * c)) / (2 * a)

        # rounded up minimum turning radius, constraint by inner- and outer streamers
        self.vesselTurningRadius = max(2500.0, 100.0 * math.ceil(0.01 * max(self.innerTurningRadius, self.outerTurningRadius)))

        self.featherAngle = math.degrees(math.asin(self.crossCurrent / self.vesselSpeed))
        self.effectiveSpeed = math.degrees(math.acos(self.crossCurrent / self.vesselSpeed))
