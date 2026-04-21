from qgis.PyQt.QtGui import QColor

from .roll_block import RollBlock
from .roll_seed import RollSeed
from .roll_template import RollTemplate

SOURCE_SEED_COLOR = '#77ff0000'
RECEIVER_SEED_COLOR = '#7700b0f0'


def createSurveySeed(name, survey=None, *, bSource=False, color=None):
    seed = RollSeed(name)
    if survey is not None:
        seed.setSurvey(survey)

    seed.bSource = bSource
    if color is not None:
        seed.color = QColor(color)
    return seed


def createAppendedTemplateSeed(name, existingSeeds, survey=None):
    haveReceiverSeed = any(seed.bSource is False for seed in existingSeeds)
    if haveReceiverSeed:
        return createSurveySeed(name, survey, bSource=True, color=SOURCE_SEED_COLOR)
    return createSurveySeed(name, survey, bSource=False, color=RECEIVER_SEED_COLOR)


def createDefaultTemplate(name='template-1', survey=None):
    template = RollTemplate(name)
    template.seedList.append(createSurveySeed('Seed-1', survey, bSource=True, color=SOURCE_SEED_COLOR))
    template.seedList.append(createSurveySeed('Seed-2', survey, bSource=False, color=RECEIVER_SEED_COLOR))
    return template


def createDefaultBlock(name='block-1', survey=None):
    block = RollBlock(name)
    block.templateList.append(createDefaultTemplate(survey=survey))
    return block
