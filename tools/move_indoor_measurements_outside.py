##Roll scripts=group                            # noqa: E265
##move_indoor_measurements_outside=name         # noqa: E265


import math

from qgis.core import (QgsFeature, QgsFeatureSink, QgsField, QgsFields,
                       QgsGeometry, QgsPointXY, QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber, QgsProject, QgsSettings,
                       QgsSpatialIndex)
from qgis.PyQt.QtCore import QVariant


class MoveIndoorPointsOutside(QgsProcessingAlgorithm):

    POINTS = "POINTS"
    BUILDINGS = "BUILDINGS"
    OFFSET = "OFFSET"
    OUTPUT = "OUTPUT"

    SETTINGS_KEY_POINTS = "roll/move_indoor_measurements_outside/points_source"
    SETTINGS_KEY_BUILDINGS = "roll/move_indoor_measurements_outside/buildings_source"
    SETTINGS_KEY_OFFSET = "roll/move_indoor_measurements_outside/offset"
    SETTINGS_KEY_POINTS_LAYER_ID = "roll/move_indoor_measurements_outside/points_layer_id"
    SETTINGS_KEY_BUILDINGS_LAYER_ID = "roll/move_indoor_measurements_outside/buildings_layer_id"

    def initAlgorithm(self, config=None):

        settings = QgsSettings()
        default_points_layer_id = settings.value(self.SETTINGS_KEY_POINTS_LAYER_ID, "", type=str)
        default_buildings_layer_id = settings.value(self.SETTINGS_KEY_BUILDINGS_LAYER_ID, "", type=str)
        default_points = settings.value(self.SETTINGS_KEY_POINTS, "", type=str)
        default_buildings = settings.value(self.SETTINGS_KEY_BUILDINGS, "", type=str)
        default_offset = settings.value(self.SETTINGS_KEY_OFFSET, 2.0, type=float)

        # Prefer project layer IDs for stable restore in QGIS layer pickers.
        default_points_value = None
        default_buildings_value = None

        project = QgsProject.instance()
        if default_points_layer_id and project.mapLayer(default_points_layer_id) is not None:
            default_points_value = default_points_layer_id
        elif default_points:
            default_points_value = default_points

        if default_buildings_layer_id and project.mapLayer(default_buildings_layer_id) is not None:
            default_buildings_value = default_buildings_layer_id
        elif default_buildings:
            default_buildings_value = default_buildings

        if not default_points_value:
            default_points_value = None
        if not default_buildings_value:
            default_buildings_value = None

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS,
                "Measurement points",
                [QgsProcessing.TypeVectorPoint],
                defaultValue=default_points_value
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BUILDINGS,
                "Building polygons",
                [QgsProcessing.TypeVectorPolygon],
                defaultValue=default_buildings_value
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.OFFSET,
                "Final distance OUTSIDE the building wall (meters)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=default_offset
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Corrected measurement points"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        points = self.parameterAsSource(parameters, self.POINTS, context)
        buildings = self.parameterAsSource(parameters, self.BUILDINGS, context)
        offset = self.parameterAsDouble(parameters, self.OFFSET, context)

        settings = QgsSettings()
        points_layer = self.parameterAsVectorLayer(parameters, self.POINTS, context)
        buildings_layer = self.parameterAsVectorLayer(parameters, self.BUILDINGS, context)

        if points_layer is not None:
            settings.setValue(self.SETTINGS_KEY_POINTS_LAYER_ID, points_layer.id())
            settings.setValue(self.SETTINGS_KEY_POINTS, points_layer.source())
        if buildings_layer is not None:
            settings.setValue(self.SETTINGS_KEY_BUILDINGS_LAYER_ID, buildings_layer.id())
            settings.setValue(self.SETTINGS_KEY_BUILDINGS, buildings_layer.source())
        settings.setValue(self.SETTINGS_KEY_OFFSET, float(offset))

        out_fields = QgsFields(points.fields())
        out_fields.append(QgsField("was_moved", QVariant.String))
        out_fields.append(QgsField("distance_moved", QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            points.wkbType(),
            points.sourceCrs()
        )

        # Spatial index for buildings
        b_index = QgsSpatialIndex()
        building_dict = {}
        for bfeat in buildings.getFeatures():
            b_index.insertFeature(bfeat)
            building_dict[bfeat.id()] = bfeat

        def true_penetration_and_normal(point_geom, building_geom):

            P = point_geom.asPoint()
            vertices = list(building_geom.vertices())

            best_dist = float("inf")
            best_normal = (1.0, 0.0)

            for i, p1 in enumerate(vertices):
                p2 = vertices[(i + 1) % len(vertices)]

                # segment vector
                vx = p2.x() - p1.x()
                vy = p2.y() - p1.y()

                # perpendicular normals
                nx1, ny1 = -vy, vx
                nx2, ny2 = vy, -vx

                # normalize
                def norm(x, y):
                    length = math.sqrt(x * x + y * y)
                    return (x / length, y / length) if length != 0 else (1, 0)

                nx1, ny1 = norm(nx1, ny1)
                nx2, ny2 = norm(nx2, ny2)

                # distance from point to segment
                # using projection formula
                px, py = P.x(), P.y()
                sx, sy = p1.x(), p1.y()
                ex, ey = p2.x(), p2.y()

                seg_len2 = (ex - sx)**2 + (ey - sy)**2
                if seg_len2 == 0:
                    continue

                t = ((px - sx) * (ex - sx) + (py - sy) * (ey - sy)) / seg_len2
                t = max(0, min(1, t))

                closest_x = sx + t * (ex - sx)
                closest_y = sy + t * (ey - sy)

                dist = math.sqrt((px - closest_x)**2 + (py - closest_y)**2)

                if dist < best_dist:
                    best_dist = dist
                    best_normal = (nx1, ny1)  # pick one normal; direction tested later

            return best_dist, best_normal

        def move_point_outside(point_geom, building_geom, offset_dist):

            penetration, (nx, ny) = true_penetration_and_normal(point_geom, building_geom)

            total_move = penetration + offset_dist
            P = point_geom.asPoint()

            cand1 = QgsPointXY(P.x() + nx * total_move, P.y() + ny * total_move)
            cand2 = QgsPointXY(P.x() - nx * total_move, P.y() - ny * total_move)

            # choose the one outside
            if not building_geom.contains(QgsGeometry.fromPointXY(cand1)):
                return cand1
            else:
                return cand2

        for feat in points.getFeatures():
            geom = feat.geometry()

            candidate_ids = b_index.intersects(geom.boundingBox())

            inside = False
            nearest_building = None

            for bid in candidate_ids:
                bfeat = building_dict[bid]
                bgeom = bfeat.geometry()

                if geom.within(bgeom):
                    inside = True
                    nearest_building = bfeat
                    break

            if not inside:
                new_feat = QgsFeature(out_fields)
                new_feat.setGeometry(geom)
                new_feat.setAttributes(feat.attributes() + ["no", 0.0])
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)
                continue

            corrected_pt = move_point_outside(geom, nearest_building.geometry(), offset)
            corrected_geom = QgsGeometry.fromPointXY(corrected_pt)
            dist = geom.distance(corrected_geom)

            new_feat = QgsFeature(out_fields)
            new_feat.setGeometry(corrected_geom)
            new_feat.setAttributes(feat.attributes() + ["yes", dist])
            sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: dest_id}

    def name(self):
        return "move_indoor_measurements_outside"

    def displayName(self):
        return "Move indoor measurements outside"

    def group(self):
        return "Roll scripts"

    def groupId(self):
        return "rollscripts"

    def createInstance(self):
        return MoveIndoorPointsOutside()
