# import qgis libs so that we set the correct sip api version
from .qgis_bootstrap import ensureQgisAvailable

if not ensureQgisAvailable():
    raise ModuleNotFoundError('qgis')

import qgis  # pylint: disable=W0611,C0411,C0413  # NOQA
