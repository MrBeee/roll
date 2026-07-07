# Not used yet, but could be useful in the future

##Clean and Snap Points to Roads=name           # noqa: E265
##POINTS=vector point                           # noqa: E265
##ROADS=vector line                             # noqa: E265
##TOLERANCE=number 300                          # noqa: E265

import processing
from qgis.core import (QgsCoordinateReferenceSystem, QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber)


class CleanSnapPointsToRoads(QgsProcessingAlgorithm):

    PARAM_POINTS = "POINTS"
    PARAM_ROADS = "ROADS"
    PARAM_TOLERANCE = "TOLERANCE"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARAM_POINTS,
                "Measurement points",
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARAM_ROADS,
                "OSM road layer",
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.PARAM_TOLERANCE,
                "Snapping tolerance (meters)",
                QgsProcessingParameterNumber.Double,
                300
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Snapped points"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        points = self.parameterAsSource(parameters, self.PARAM_POINTS, context)
        roads = self.parameterAsSource(parameters, self.PARAM_ROADS, context)
        tolerance = self.parameterAsDouble(parameters, self.PARAM_TOLERANCE, context)

        feedback.pushInfo("Step 1: Multipart → Singleparts")
        singleparts = processing.run(
            "native:multiparttosingleparts",
            {
                "INPUT": roads,
                "OUTPUT": "memory:singleparts"
            },
            context=context,
            feedback=feedback
        )["OUTPUT"]

        feedback.pushInfo("Step 2: Remove construction roads")
        filtered1 = processing.run(
            "native:extractbyattribute",
            {
                "INPUT": singleparts,
                "FIELD": "highway",
                "OPERATOR": 0,  # !=
                "VALUE": "construction",
                "OUTPUT": "memory:filtered1"
            },
            context=context,
            feedback=feedback
        )["OUTPUT"]

        feedback.pushInfo("Step 3: Remove proposed roads")
        filtered2 = processing.run(
            "native:extractbyattribute",
            {
                "INPUT": filtered1,
                "FIELD": "highway",
                "OPERATOR": 0,  # !=
                "VALUE": "proposed",
                "OUTPUT": "memory:filtered2"
            },
            context=context,
            feedback=feedback
        )["OUTPUT"]

        feedback.pushInfo("Step 4: Reproject roads to EPSG:25832")
        reprojected = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": filtered2,
                "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:25832"),
                "OUTPUT": "memory:roads_25832"
            },
            context=context,
            feedback=feedback
        )["OUTPUT"]

        feedback.pushInfo("Step 5: Snap points to nearest road segment")
        snapped = processing.run(
            "native:snapgeometries",
            {
                "INPUT": points,
                "REFERENCE_LAYER": reprojected,
                "BEHAVIOR": 0,  # Prefer closest point
                "TOLERANCE": tolerance,
                "OUTPUT": parameters[self.OUTPUT]
            },
            context=context,
            feedback=feedback
        )[self.OUTPUT]

        return {self.OUTPUT: snapped}


# Instantiate the algorithm
CleanSnapPointsToRoads()
