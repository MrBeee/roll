# Not used yet, but could be useful in the future

##Clean and Snap Points to Roads=name           # noqa: E265
##POINTS=vector point                           # noqa: E265
##ROADS=vector line                             # noqa: E265
##TOLERANCE=number 300                          # noqa: E265

import processing
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber, QgsProject, QgsSettings)


class CleanSnapPointsToRoads(QgsProcessingAlgorithm):

    PARAM_POINTS = "POINTS"
    PARAM_ROADS = "ROADS"
    PARAM_TOLERANCE = "TOLERANCE"
    PARAM_MULTIPART_TO_SINGLEPARTS = "MULTIPART_TO_SINGLEPARTS"
    PARAM_REMOVE_CONSTRUCTION_PROPOSED = "REMOVE_CONSTRUCTION_PROPOSED"
    OUTPUT = "OUTPUT"

    SETTINGS_KEY_POINTS = "roll/clean_and_snap_points_to_roads/points_source"
    SETTINGS_KEY_ROADS = "roll/clean_and_snap_points_to_roads/roads_source"
    SETTINGS_KEY_TOLERANCE = "roll/clean_and_snap_points_to_roads/tolerance"
    SETTINGS_KEY_POINTS_LAYER_ID = "roll/clean_and_snap_points_to_roads/points_layer_id"
    SETTINGS_KEY_ROADS_LAYER_ID = "roll/clean_and_snap_points_to_roads/roads_layer_id"
    SETTINGS_KEY_MULTIPART_TO_SINGLEPARTS = "roll/clean_and_snap_points_to_roads/multipart_to_singleparts"
    SETTINGS_KEY_REMOVE_CONSTRUCTION_PROPOSED = "roll/clean_and_snap_points_to_roads/remove_construction_proposed"

    @staticmethod
    def _readBoolSetting(settings, key, defaultValue):
        value = settings.value(key, None)
        if value is None:
            return bool(defaultValue)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return bool(value)

    def initAlgorithm(self, config=None):

        _ = config

        settings = QgsSettings()
        default_points_layer_id = settings.value(self.SETTINGS_KEY_POINTS_LAYER_ID, "", type=str)
        default_roads_layer_id = settings.value(self.SETTINGS_KEY_ROADS_LAYER_ID, "", type=str)
        default_points = settings.value(self.SETTINGS_KEY_POINTS, "", type=str)
        default_roads = settings.value(self.SETTINGS_KEY_ROADS, "", type=str)
        default_tolerance = settings.value(self.SETTINGS_KEY_TOLERANCE, 300.0, type=float)
        default_multipart_to_singleparts = self._readBoolSetting(settings, self.SETTINGS_KEY_MULTIPART_TO_SINGLEPARTS, True)
        default_remove_construction_proposed = self._readBoolSetting(settings, self.SETTINGS_KEY_REMOVE_CONSTRUCTION_PROPOSED, True)

        # Prefer project layer IDs for stable restore in QGIS layer pickers.
        default_points_value = None
        default_roads_value = None

        project = QgsProject.instance()
        if default_points_layer_id and project.mapLayer(default_points_layer_id) is not None:
            default_points_value = default_points_layer_id
        elif default_points:
            default_points_value = default_points

        if default_roads_layer_id and project.mapLayer(default_roads_layer_id) is not None:
            default_roads_value = default_roads_layer_id
        elif default_roads:
            default_roads_value = default_roads

        if not default_points_value:
            default_points_value = None
        if not default_roads_value:
            default_roads_value = None

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARAM_POINTS,
                "Measurement points",
                [QgsProcessing.TypeVectorPoint],
                defaultValue=default_points_value
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARAM_ROADS,
                "OSM road layer",
                [QgsProcessing.TypeVectorLine],
                defaultValue=default_roads_value
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.PARAM_TOLERANCE,
                "Snapping tolerance (meters)",
                QgsProcessingParameterNumber.Double,
                default_tolerance
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.PARAM_MULTIPART_TO_SINGLEPARTS,
                "Step 1: Multipart -> Singlepart OSM road segments",
                defaultValue=default_multipart_to_singleparts
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.PARAM_REMOVE_CONSTRUCTION_PROPOSED,
                "Step 2: Remove proposed roads and roads under construction",
                defaultValue=default_remove_construction_proposed
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Snapped points"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        points = self.parameterAsVectorLayer(parameters, self.PARAM_POINTS, context)
        roads = self.parameterAsVectorLayer(parameters, self.PARAM_ROADS, context)
        tolerance = self.parameterAsDouble(parameters, self.PARAM_TOLERANCE, context)
        run_multipart_to_singleparts = self.parameterAsBool(parameters, self.PARAM_MULTIPART_TO_SINGLEPARTS, context)
        run_remove_construction_proposed = self.parameterAsBool(parameters, self.PARAM_REMOVE_CONSTRUCTION_PROPOSED, context)

        settings = QgsSettings()

        if points is None:
            raise ValueError("Could not load measurement points layer")

        if roads is None:
            raise ValueError("Could not load roads layer")

        settings.setValue(self.SETTINGS_KEY_POINTS_LAYER_ID, points.id())
        settings.setValue(self.SETTINGS_KEY_POINTS, points.source())
        settings.setValue(self.SETTINGS_KEY_ROADS_LAYER_ID, roads.id())
        settings.setValue(self.SETTINGS_KEY_ROADS, roads.source())
        settings.setValue(self.SETTINGS_KEY_TOLERANCE, float(tolerance))
        settings.setValue(self.SETTINGS_KEY_MULTIPART_TO_SINGLEPARTS, bool(run_multipart_to_singleparts))
        settings.setValue(self.SETTINGS_KEY_REMOVE_CONSTRUCTION_PROPOSED, bool(run_remove_construction_proposed))

        referenceLayer = roads

        if run_multipart_to_singleparts:
            feedback.pushInfo("Step 1: Multipart -> Singleparts")
            referenceLayer = processing.run(
                "native:multiparttosingleparts",
                {
                    "INPUT": referenceLayer,
                    "OUTPUT": "memory:singleparts"
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )["OUTPUT"]
        else:
            feedback.pushInfo("Step 1 skipped: using roads layer as-is")

        if run_remove_construction_proposed:
            feedback.pushInfo("Step 2: Remove construction roads")
            filtered1 = processing.run(
                "native:extractbyattribute",
                {
                    "INPUT": referenceLayer,
                    "FIELD": "highway",
                    "OPERATOR": 1,  # !=
                    "VALUE": "construction",
                    "OUTPUT": "memory:filtered1"
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )["OUTPUT"]

            feedback.pushInfo("Step 2: Remove proposed roads")
            filtered2 = processing.run(
                "native:extractbyattribute",
                {
                    "INPUT": filtered1,
                    "FIELD": "highway",
                    "OPERATOR": 1,  # !=
                    "VALUE": "proposed",
                    "OUTPUT": "memory:filtered2"
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )["OUTPUT"]
            referenceLayer = filtered2
        else:
            feedback.pushInfo("Step 2 skipped: construction/proposed roads are retained")

        if hasattr(referenceLayer, "featureCount") and referenceLayer.featureCount() == 0:
            feedback.pushWarning("Filtered roads layer is empty; falling back to unfiltered singlepart roads for snapping")
            if run_multipart_to_singleparts:
                referenceLayer = processing.run(
                    "native:multiparttosingleparts",
                    {
                        "INPUT": roads,
                        "OUTPUT": "memory:singleparts_fallback"
                    },
                    context=context,
                    feedback=feedback,
                    is_child_algorithm=True
                )["OUTPUT"]
            else:
                referenceLayer = roads

        feedback.pushInfo("Step 3: Snap points to nearest road segment")
        snapped = processing.run(
            "native:snapgeometries",
            {
                "INPUT": points,
                "REFERENCE_LAYER": referenceLayer,
                "BEHAVIOR": 1,  # Prefer closest point, insert extra vertices where required
                "TOLERANCE": tolerance,
                "OUTPUT": parameters[self.OUTPUT]
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )[self.OUTPUT]

        return {self.OUTPUT: snapped}

    def name(self):
        return "clean_and_snap_points_to_roads"

    def displayName(self):
        return "Clean and snap points to roads"

    def group(self):
        return "Roll scripts"

    def groupId(self):
        return "rollscripts"

    def createInstance(self):
        return CleanSnapPointsToRoads()


# Instantiate the algorithm
CleanSnapPointsToRoads()
