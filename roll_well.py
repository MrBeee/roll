import os

import numpy as np
import wellpathpy as wp
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY, QgsProject, QgsVector3D
from qgis.PyQt.QtCore import QFileInfo, QPointF
from qgis.PyQt.QtGui import QPolygonF, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from . import config  # used to pass initial settings
from .functions import toFloat, toInt
from .rdp import filterRdp


class RollWell:
    # assign default name
    def __init__(self, name: str = '') -> None:
        # input variables
        self.name = name                                                        # path to well file
        self.errorText = None                                                   # text explaining which error occurred

        if config.surveyCrs is not None and config.surveyCrs.isValid():         # copy crs from project
            self.crs = config.surveyCrs
        else:
            self.crs = QgsCoordinateReferenceSystem('EPSG:23095')               # ED50 / TM 5 NE (arbitrarily chosen)

        self.ahd0 = 1000.0                                                      # first (along hole) depth
        self.dAhd = 15.0                                                        # along hole depth increment
        self.nAhd = 12                                                          # nr of along hole stations

        # variables, calculated and serialized
        self.ahdMax = -999.0                                                    # ahd max, used to set limits for ahd0 and nAhd
        self.origW = QVector3D(-999.0, -999.0, -999.0)                          # wellhead location in original well coordinates
        self.origG = QPointF(-999.0, -999.0)                                    # wellhead location in global project coordinates
        self.origL = QPointF(-999.0, -999.0)                                    # wellhead location in local project coordinates

        # variables, calculated but not serialized
        # self.polygon = QPolygonF()                                              # polygon in local coordinates, to draw well trajectory; start empty
        self.polygon = None                                                     # QPolygonF() in local coordinates, to draw well trajectory; start with None
        self.pntList2D = []                                                     # points  in local coordinates, to draw well trajectory; start empty

        # please note the seed's origin is hidden in the property editor, when using a well-based seed
        # instead, the well's origin is shown in 3 different CRSes; (a) well (b) global survey (c) local survey
        # in the xml file, the seed origin is shown in the local survey coordinates

        # for self.lod0 See: https://python.hotexamples.com/examples/PyQt5.QtGui/QPainter/drawPolyline/python-qpainter-drawpolyline-method-examples.html

    def readHeader(self, surveyCrs, glbTransform):
        header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
        self.errorText = None                                                   # text explaining which error occurred

        f = self.name
        if f is None or not os.path.exists(f):                                  # check filename first
            self.errorText = 'No valid well file selected'
            return False

        if not self.crs.isValid():                                              # then check CRS
            self.errorText = 'An invalid CRS has been selected'
            return False

        if self.crs.isGeographic():
            self.errorText = 'geographic CRS selected (using lat/lon angles)'
            return False

        ext = QFileInfo(f).suffix()

        try:
            if ext == 'wws':                                                        # read the well survey file
                md, _, _ = wp.read_csv(f, delimiter=None, skiprows=0, comments='#')   # inc, azi unused and replaced by _, _
                self.ahdMax = md[-1]                                                # maximum along-hole-depth

                # where is the well located ? First see if there's a header file, to pull information from.
                hdrFile = os.path.splitext(f)[0]
                hdrFile = hdrFile + '.hdr'
                # open the header file
                if os.path.exists(hdrFile):
                    # read header in json format
                    header = wp.read_header_json(hdrFile)
                else:
                    # get header information from wws-file itself
                    header = self.readWwsHeader()

            elif ext == 'well':
                header, index = self.readWellHeader()

                # read the 4 column ascii data; skip header rows
                pos2D = np.loadtxt(f, delimiter=None, skiprows=index, comments='!')

                # transpose array to 4 rows, and read these rows
                _, _, depth, md = pos2D.T

                # determine maximum along-hole-depth
                self.ahdMax = md[-1]

                # the self-contained 'well' file does not require a separate header file;
                hdrFile = os.path.splitext(f)[0]

                # but a header file could be used to override the included header data
                hdrFile = hdrFile + '.hdr'
                if os.path.exists(hdrFile):
                    # read header in json format, as described in header dict above
                    header = wp.read_header_json(hdrFile)

                # no separate header file has been provided
                if header['elevation'] is None:
                    header['elevation'] = md[0] - depth[0]
            else:
                self.errorText = f'unsupported file extension: {ext}'
                return False

        except BaseException as e:
            self.errorText = str(e)
            return False

        if header['surface_easting'] is None or header['surface_northing'] is None or header['elevation'] is None:
            self.errorText = 'invalid or missing file header'
            return False

        self.origW = QVector3D(header['surface_easting'], header['surface_northing'], header['elevation'])

        # note: if survey's crs and well's crs are the same, the wellToGlobalTransform has no effect
        wellToGlobalTransform = QgsCoordinateTransform(surveyCrs, self.crs, QgsProject.instance())

        if not wellToGlobalTransform.isValid():                                 # no valid transform found
            self.errorText = 'invalid coordinate transform'
            return False

        # now create the origin in global survey coordinates (well-crs -> project-crs)
        x0, y0 = wellToGlobalTransform.transform(header['surface_easting'], header['surface_northing'])

        x0 = round(x0, 2)
        y0 = round(y0, 2)
        self.origG = QPointF(x0, y0)

        # create transform from global- to survey coordinates
        toLocalTransform, _ = glbTransform.inverted()

        # convert orig from global- to local coordinates
        self.origL = toLocalTransform.map(self.origG)
        self.origL.setX(round(self.origL.x(), 2))
        self.origL.setY(round(self.origL.y(), 2))

        return True

    def readWellHeader(self):
        header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
        # Note: datum = kb (kelly bushing), dfe (drill floor elevation), or rt (rotary table)

        # need to adjust northing and easting and elevation; use keywords from the well file itself
        keywords = ['Depth-Unit:', 'UniqOff Well ID:', 'Operator:', 'State:', 'County:', 'Surface coordinate:', 'Replacement velocity [from KB to SRD]:']

        with open(self.name, 'r', encoding='utf-8') as file:
            nExclamation = 0
            index = 0
            for index, line in enumerate(file):
                if line.startswith('!'):
                    nExclamation += 1
                    if nExclamation == 2:
                        break                                               # time to start reading the data
                    else:
                        continue

                for i, k in enumerate(keywords):
                    if k in line:
                        val = line.split(':')                               # behind ':' sits the keyword value
                        val = val[1].split('\n')                            # if keyword value followed by \n, get rid of it
                        val = val[0].strip()    	                        # turn list into string, get rid of leading/trailing spaces

                        print('line:', index + 1, 'keyword nr:', i + 1, 'keyword:', k, 'value:', val)

                        if i == 0:
                            header['elevation_units'] = val.lower()[0]
                            header['surface_coordinates_units'] = 'm'       # actually should be equal to coordinate units of CRS; could be feet
                        if i == 5:
                            val = val.strip(' ()')
                            val = val.split(',')
                            header['surface_northing'] = float(val[1])
                            header['surface_easting'] = float(val[0])
        return header, index

    def readWwsHeader(self):
        header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
        # Note: datum = kb (kelly bushing), dfe (drill floor elevation), or rt (rotary table)

        # need to adjust northing and easting and elevation; use keywords from the well file itself
        keywords = ['$Wellbore_name:', '$Well_name:', '$Status_of_Well:', '$Well_northing:', '$Well_easting:', '$Derrick_elevation:']
        # example output
        # 0 $Wellbore_name: PR01
        # 1 $Well_name: PR01
        # 2 $Status_of_Well: EXISTING
        # 3 $Well_northing: 7623750.00
        # 4 $Well_easting: 185250.00
        # 5 $Derrick_elevation: 0.00

        with open(self.name, 'r', encoding='utf-8') as file:
            for index, line in enumerate(file):
                if not line.startswith('#'):
                    break
                for i, k in enumerate(keywords):
                    if k in line:
                        val = line.split(':')                                   # behind ':' sits the keyword value
                        val = val[1].split('\n')                                # if keyword value followed by \n, get rid of it
                        val = val[0].split('[')                                 # if keyword value followed by '[', get rid of what follows
                        if len(val) > 1:
                            unit = val[1].split(']')[0]
                        else:
                            unit = None
                        val = val[0].strip()    	                            # turn list into string, get rid of leading/trailing spaces
                        print('line:', index + 1, 'keyword nr:', i + 1, 'keyword:', k, 'value:', val, 'unit:', unit)
                        if i == 3:
                            header['surface_northing'] = float(val)
                            header['surface_coordinates_units'] = unit
                        if i == 4:
                            header['surface_easting'] = float(val)
                        if i == 5:
                            header['elevation'] = float(val)
                            header['elevation_units'] = unit
        return header

    def deviationFromXYZ(self, northing, easting, depth):
        """Deviation survey

        Compute an approximate deviation survey from the position log, i.e. the
        measured that would be convertable to this well path. It is assumed
        that inclination, azimuth, and measured-depth starts at 0.

        Returns
        -------
        dev : deviation

        The implementation is based on this [1] stackexchange answer by tma,
        which is included verbatim for future reference.

            In order to get a better picture you should look at the problem in
            2d. Your arc from (x1,y1,z1) to (x2,y2,z2) lives in a 2d plane,
            also in the same pane the tangents (a1,i1) and (a2, i2). The 2d
            plane is given by the vector (x1,y1,y3) to (x2,y2,z2) and vector
            converted from polar to Cartesian of (a1, i1). In case their
            co-linear is just a straight line and your done. Given the angle
            between the (x1,y1,z2) and (a1, i1) be alpha, then the angle
            between (x2,y2,z2) and (a2, i2) is â€“alpha. Use the normal vector of
            the 2d plane and rotate normalized vector (x1,y1,z1) to (x2,y2,z2)
            by alpha (maybe â€“alpha) and converter back to polar coordinates,
            which gives you (a2,i2). If d is the distance from (x1,y1,z1) to
            (x2,y2,z2) then MD = d* alpha /sin(alpha).

        In essence, the well path (in cartesian coordinates) is evaluated in
        segments from top to bottom, and for every segment the inclination and
        azimuth "downwards" are reconstructed. The reconstructed inc and azi is
        used as "entry angle" of the well bore into the next segment. This uses
        some assumptions deriving from knowing that the position log was
        calculated with the min-curve method, since a straight
        cartesian-to-spherical conversion could be very sensitive [2].

        [1] https://math.stackexchange.com/a/1191620
        [2] I observed low error on average, but some segments could be off by
            80 degrees azimuth
        """
        upper = zip(northing[:-1], easting[:-1], depth[:-1])
        lower = zip(northing[1:], easting[1:], depth[1:])

        # Assume the initial depth and angles are all zero, but this can likely
        # be parametrised.
        incs, azis, mds = [0], [0], [0]
        i1, a1 = 0, 0

        for up, lo in zip(upper, lower):
            up = np.array(up)
            lo = np.array(lo)

            # Make two vectors
            # v1 is the vector from the upper survey station to the lower
            # v2 is the vector formed by the initial inc/azi (given by the
            # previous iteration).
            #
            # The v1 and v2 vectors form a plane the well path arc lives in.
            v1 = lo - up
            v2 = np.array(wp.geometry.direction_vector(i1, a1))

            alpha = wp.geometry.angle_between(v1, v2)
            normal = wp.geometry.normal_vector(v1, v2)

            # v3 is the "exit vector", i.e. the direction of the well bore
            # at the lower survey station, which would in turn be "entry
            # direction" in the next segment.
            v3 = wp.geometry.rotate(v1, normal, -alpha)
            i2, a2 = wp.geometry.spherical(*v3)

            # d is the length of the vector (straight line) from the upper
            # station to the lower station.
            d = np.linalg.norm(v1)
            incs.append(i2)
            azis.append(a2)
            if alpha == 0:
                mds.append(d)
            else:
                mds.append(d * alpha / np.sin(alpha))
            # The current lower station is the upper station in the next
            # segment.
            i1 = i2
            a1 = a2

        mds = np.cumsum(mds)
        return wp.deviation(md=np.array(mds), inc=np.array(incs), azi=np.array(azis))

    def calcPointList(self, surveyCrs, glbTransform):
        # See: https://stackoverflow.com/questions/49322017/merging-1d-arrays-into-a-2d-array
        # See: https://www.appsloveworld.com/numpy/100/17/how-can-i-efficiently-transfer-data-from-a-numpy-array-to-a-qpolygonf-when-using
        # See: https://stackoverflow.com/questions/5081875/ctypes-beginner for working with ctypes

        success = self.readHeader(surveyCrs, glbTransform)
        if not success:
            return [], QVector3D(-999.0, -999.0, -999.0)

        f = self.name
        a = self.ahd0
        s = self.dAhd
        n = self.nAhd
        td = a + (n - 1) * s

        # note: if survey's crs and well's crs are the same, the wellToGlobalTransform has no effect
        wellToGlobalTransform = QgsCoordinateTransform(surveyCrs, self.crs, QgsProject.instance())

        # create transform from global- to local coordinates
        toLocalTransform, _ = glbTransform.inverted()

        # create list of available ahd-depth-levels that show source/sensor positions
        ahdList = list(np.linspace(a, td, num=n))

        ext = QFileInfo(f).suffix()

        try:
            if ext == 'wws':                                                        # read contents well survey file
                md, inc, azi = wp.read_csv(f, delimiter=None, skiprows=0, comments='#')

                # get an approximate deviation survey from the position log
                dev = wp.deviation(md=md, inc=inc, azi=azi)
            elif ext == 'well':
                _, index = self.readWellHeader()                                      # need index to get to the data

                # read the 4 column ascii data; skip header rows
                pos2D = np.loadtxt(f, delimiter=None, skiprows=index, comments='!')

                north, east, depth, md = pos2D.T                                    # transpose array to 4 rows, and read these rows
                self.ahdMax = md[-1]                                                # maximum along-hole-depth

                # for next line; see position_log.py line 409 and further in imported module wellpathpy
                # from here, things are the same as for the wws solution
                dev = self.deviationFromXYZ(north, east, depth)
            else:
                raise ValueError(f'unsupported file extension: {ext}')

        except BaseException as e:
            self.errorText = str(e)
            return [], QVector3D(-999.0, -999.0, -999.0)

        # this is the key routine that resamples a well trajectory into (x, y, z) values
        pos = dev.minimum_curvature().resample(depths=ahdList)
        pos_wellhead = pos.to_wellhead(surface_northing=self.origW.y(), surface_easting=self.origW.x())
        pos_tvdss = pos_wellhead.to_tvdss(datum_elevation=self.origW.z())

        x = pos_tvdss.easting
        y = pos_tvdss.northing
        z = pos_tvdss.depth
        n = len(x)

        # first create the list of 3D points in survey coordinates (well-crs -> project-crs -> survey grid)

        pointList = []                                                          # points to derive cdp coverage from
        for i in range(n):                                                      # iterate over all points
            # use 3D values; survey points reside below surface in a well
            vector = QgsVector3D(x[i], y[i], z[i])

            # wellToGlobalTransform may affect elevation
            vector = wellToGlobalTransform.transform(vector)

            # z-value not used in toLocalTransform
            pnt2D = QPointF(vector.x(), vector.y())

            # convert 2D point from global coordinates to survey coordinates
            pnt2D = toLocalTransform.map(pnt2D)

            # create 3D point to be added to list after survey transform
            pnt3D = QVector3D(pnt2D.x(), pnt2D.y(), vector.z())

            # points to derive cdp coverage from
            pointList.append(pnt3D)

        # now display the well trajectory; use 2D points in local coordinates (well-crs -> project-crs -> local grid)
        steps = 50                                                              # start with 50 points along trajectory
        displayList = list(range(0, int(dev.md[-1]) + 1, steps))                # range only likes int values

        # this is the key routine that resamples to (x, y, z) values
        pos = dev.minimum_curvature().resample(depths=displayList)              # use minimum curvature interpolation
        pos_wellhead = pos.to_wellhead(surface_northing=self.origW.y(), surface_easting=self.origW.x())
        pos_tvdss = pos_wellhead.to_tvdss(datum_elevation=self.origW.z())

        data = list(zip(pos_tvdss.easting, pos_tvdss.northing))                 # create list with (x, y) pairs

        # create mask point list with 2.5 m accuracy
        mask = filterRdp(data, threshold=2.5)                                   # create a numpy mask

        # apply the mask and reduce mumber of points
        data = np.array(data)[mask]                                             # apply the mask

        # the (reduced) data points are still in well-crs coordinates
        self.pntList2D = []                                                     # points to display on map

        # create polygon to draw well trajectory
        self.polygon = QPolygonF()
        for p in data:                                                          # using point iterator
            # wellToGlobalTransform may affect elevation
            pnt2D = wellToGlobalTransform.transform(QgsPointXY(*p)).toQPointF()

            # convert 2D point from global coordinates to survey coordinates
            pnt2D = toLocalTransform.map(pnt2D)

            # points to display on map
            self.pntList2D.append(pnt2D)

            # add points to polygon
            self.polygon.append(pnt2D)

        # return list and well origin in local coordinates; borrow z from well coords
        return pointList, QVector3D(self.origL.x(), self.origL.y(), self.origW.z())

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        wellElem = doc.createElement('well')

        if self.name is None or self.name == '':
            self.name = 'None'

        # if not self.name is None and len(self.name) > 0:
        nameElement = doc.createElement('name')
        text = doc.createTextNode(self.name)
        nameElement.appendChild(text)
        wellElem.appendChild(nameElement)

        wellElem.setAttribute('ds', str(self.dAhd))
        wellElem.setAttribute('ns', str(self.nAhd))
        wellElem.setAttribute('s0', str(self.ahd0))
        wellElem.setAttribute('smax', str(self.ahdMax))

        wellElem.setAttribute('wx', str(round(self.origW.x(), 2)))
        wellElem.setAttribute('wy', str(round(self.origW.y(), 2)))
        wellElem.setAttribute('wz', str(round(self.origW.z(), 2)))

        wellElem.setAttribute('gx', str(round(self.origG.x(), 2)))
        wellElem.setAttribute('gy', str(round(self.origG.y(), 2)))

        wellElem.setAttribute('lx', str(round(self.origL.x(), 2)))
        wellElem.setAttribute('ly', str(round(self.origL.y(), 2)))

        wellCrs = doc.createElement('wellCrs')
        wellElem.appendChild(wellCrs)
        if self.crs is not None:                                                # check if we have a valid crs
            # write xml-string to parent element (=surveyCrs)
            self.crs.writeXml(wellCrs, doc)

        parent.appendChild(wellElem)
        return wellElem

    def readXml(self, parent: QDomNode):
        wellElem = parent.namedItem('well').toElement()
        if wellElem.isNull():
            return False

        nameElem = wellElem.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.dAhd = toFloat(wellElem.attribute('ds'))
        self.nAhd = toInt(wellElem.attribute('ns'))
        self.ahd0 = toFloat(wellElem.attribute('s0'))
        self.ahdMax = toFloat(wellElem.attribute('smax'), -999.0)

        x0 = toFloat(wellElem.attribute('x0'), -999.0)                          # 'old' xml-attribute
        y0 = toFloat(wellElem.attribute('y0'), -999.0)                          # 'old' xml-attribute
        z0 = toFloat(wellElem.attribute('z0'), -999.0)                          # 'old' xml-attribute

        self.origW.setX(toFloat(wellElem.attribute('wx'), x0))                  # these parameters need to be calculated
        self.origW.setY(toFloat(wellElem.attribute('wy'), y0))                  # using input from a 'well file'
        self.origW.setZ(toFloat(wellElem.attribute('wz'), z0))

        self.origG.setX(toFloat(wellElem.attribute('gx'), -999.0))              # well coordinates converted to 'global' survey crs
        self.origG.setY(toFloat(wellElem.attribute('gy'), -999.0))

        hx = toFloat(wellElem.attribute('hx'), -999.0)
        hy = toFloat(wellElem.attribute('hy'), -999.0)

        self.origL.setX(toFloat(wellElem.attribute('lx'), hx))                  # 'global' well coordinates converted to local survey grid
        self.origL.setY(toFloat(wellElem.attribute('ly'), hy))

        crsElem = wellElem.namedItem('wellCrs').toElement()
        if not crsElem.isNull():
            self.crs.readXml(crsElem)

        return True
