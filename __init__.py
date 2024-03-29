"""
/***************************************************************************
 Roll
                                 A QGIS plugin
 Design and analysis of 3D seismic survey geometry
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2022-10-09
        copyright            : (C) 2022 by Duijndam.Dev
        email                : bart.duijndam@ziggo.nl
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

# import statement moved to top of file as Pylint was complaining. 
# Compare with older versions of __init__.py to see the change...
from .roll import Roll


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load Roll class from file Roll.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #

    return Roll(iface)
