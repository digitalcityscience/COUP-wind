import json
import os
import math
from geopandas.geodataframe import GeoDataFrame
import numpy as np
from typing import List
from shapely.geometry import box, Polygon, mapping, MultiPolygon

import rasterio.features
import rasterio.warp
from rasterio.transform import Affine

import geopandas
import rioxarray
from rioxarray.exceptions import NoDataInBounds as NoRioDataException
from pyproj import Transformer

from wind.cityPyo import CityPyo

# from pyproj import Transformer
transformer_to_utm = Transformer.from_crs(4326, 25832, always_xy=False).transform
transformer_to_wgs = Transformer.from_crs(25832, 4326, always_xy=True).transform


cwd = os.getcwd()
project_area_gdf = None
cityPyo = CityPyo()


# gets [x,y] of the south west corner of the bbox.
# might only work for european quadrant of the world
def get_south_west_corner_coords_of_bbox(bbox):
    import matplotlib.pyplot as plt

    longs = bbox.exterior.xy[0][0:-1]  # ignore repeated last coord
    lats = bbox.exterior.xy[1][0:-1] # ignore repeated last coord

    small_latitudes = sorted(lats)[0:2]  # the 2 most southern latitudes
    small_longitudes = sorted(longs)[0:2]  # the 2 most western longitudes

    for x, y in bbox.exterior.coords:
        if x in small_longitudes and y in small_latitudes:
            # this is our southwest corner
            return [x, y]


# return an array of dicts, each dict describing a building with simple cartesian coordinates (origin 0,0)
def get_buildings_for_bbox(bbox:Polygon, buildings_gdf: GeoDataFrame) -> list:
    buildings_in_bbox = []
    sw_x, sw_y = get_south_west_corner_coords_of_bbox(bbox) # south west corner for bbox, as utm.

    intersection_polygons = buildings_gdf.intersection(bbox)  # GeoSeries with all intersection polygons bbox<->building
    intersection_polygons = intersection_polygons.translate(-sw_x, -sw_y)  # translate to local coordinates

    intersections = buildings_gdf.copy()  # copy buildings dataframe with all properties
    intersections.geometry = intersection_polygons # replace geometry with the building intersections

    # iterate over intersections and append to buildings in bbox
    for index, row in intersections.iterrows():
        if not intersections.loc[index, 'geometry'].is_empty:
            # MultiPolygons, need to be split into normal polygons
            if type(intersections.loc[index, 'geometry']) == MultiPolygon:
                multi_geometry = json.loads(json.dumps(mapping(intersections.loc[index, 'geometry'])))
                for poly in multi_geometry["coordinates"][0]:
                    single_poly = Polygon(poly)
                    buildings_in_bbox.append({
                        "geometry": json.dumps(mapping(single_poly)),
                        "height": intersections.loc[index, 'building_height'],
                        "use": intersections.loc[index, 'land_use_detailed_type'],
                    })
            # normal polygons
            else:
                buildings_in_bbox.append({
                    "geometry": json.dumps(mapping(intersections.loc[index, 'geometry'])),
                    "height": intersections.loc[index, 'building_height'],
                    "use": intersections.loc[index, 'land_use_detailed_type'],
                })

    return buildings_in_bbox


# returns the project area as gdf
def get_project_area_as_gdf(city_pyo_user):
    global project_area_gdf
    
    # make GeoDataFrame from project area
    project_area_json = cityPyo.get_layer_for_user(city_pyo_user, "project_area")

    gdf = geopandas.GeoDataFrame.from_features(
        project_area_json["features"],
        crs=project_area_json["crs"]["properties"]["name"]
    )
    project_area_gdf = gdf

    return gdf


# returns geometry of all features of the project area GeoDataFrame
def get_project_area_polygons(city_pyo_user) -> geopandas.GeoDataFrame.geometry:
    gdf = get_project_area_as_gdf(city_pyo_user)

    return gdf.geometry


def make_gdf_from_geojson(geojson) -> geopandas.GeoDataFrame:
    gdf_cols = ["geometry"]

    # add all properties to gdf cols
    for property_key in geojson["features"][0]["properties"].keys():
        gdf_cols.append(property_key)

    try:
        crs = geojson["crs"]["properties"]["name"]
    except KeyError:
       crs="EPSG:4326" 

    gdf = geopandas.GeoDataFrame.from_features(geojson["features"], crs=crs, columns=gdf_cols)

    return gdf

# accepts arrays of coordinates (geojson format) and returns a GeoDataFrame, reprojected into utm coords
def make_gdf_from_coordinates(coordinates) -> geopandas.GeoDataFrame:
    gdf = geopandas.GeoDataFrame(
        geopandas.GeoSeries([Polygon(pol) for pol in coordinates]),
        columns=["geometry"],
        crs="EPSG:4326"
    )
    gdf = gdf.to_crs("EPSG:25832")  # reproject to utm coords

    return gdf


# subdivides the project area into a bbox matrix
# returns an array of Shapely Polygon
def init_bbox_matrix_for_project_area(city_pyo_user, bbox_size):
    # get the polygons describing the project area (e.g. the Grasbrook development area)
    project_area_polygons = get_project_area_polygons(city_pyo_user)

    bbox_matrix = []
    for pol in project_area_polygons:
        # subdivide the project area into a matrix grid
        bbox_matrix.extend(create_bbox_matrix(pol, bbox_size))

    return bbox_matrix

# creates a matrix of bboxes covering the project area polygon
def create_bbox_matrix(polygon, bbox_length) -> List[box]:
    bbox_matrix = []
    polygon_envelop = polygon.exterior.envelope

    envelop_minX = min(polygon_envelop.exterior.xy[0])
    envelop_maxX = max(polygon_envelop.exterior.xy[0])
    envelop_minY = min(polygon_envelop.exterior.xy[1])
    envelop_maxY = max(polygon_envelop.exterior.xy[1])

    # number of rows and cols of bbox matrix
    max_cols = math.floor((envelop_maxX - envelop_minX) / bbox_length) + 1
    max_rows = math.floor((envelop_maxY - envelop_minY) / bbox_length) + 1

    for row in range(0, max_rows):
        minY = envelop_minY + bbox_length * row
        maxY = minY + bbox_length
        for col in range(0, max_cols):
            minX = envelop_minX + bbox_length * col
            maxX = minX + bbox_length

            # minX, minY, maxX, maxY
            bbox = box(minX, minY, maxX, maxY)
            if polygon.intersection(bbox):
                # only add bbox to matrix, if actually intersecting with the project area polygon
                bbox_matrix.append(bbox)

    return bbox_matrix


# exports a result to geotif and returns the geotif path
def export_result_to_geotif(values, bbox_utm, project_name) -> str:
    np_values = np.array(values, dtype="float32")
    # TODO round values with around doesnt work??
    np_values = np.around(np_values, 1)
    bbox_x, bbox_y = bbox_utm.exterior.xy

    # prepare raster
    x = np.linspace(min(bbox_x), max(bbox_x), np_values.shape[0])
    y = np.linspace(min(bbox_y), max(bbox_y), np_values.shape[1])
    res_x = (x[-1] - x[0]) / np_values.shape[0]
    res_y = (x[-1] - x[0]) / np_values.shape[1]

    # Affine transformation
    transform = Affine.translation(x[0] - res_x / 2, y[0] - res_y / 2) * Affine.scale(res_x, res_y)

    # save tif to disk. It will be used for quickly clipping result to area of interest later.
    if not os.path.exists(cwd + "/tmp_tiff/"):
        os.makedirs(cwd + "/tmp_tiff/")

    file_path = cwd + "/tmp_tiff/" + project_name + ".tif"
    with rasterio.open(
            file_path,
            'w+',
            driver='GTiff',
            height=np_values.shape[0],
            width=np_values.shape[1],
            count=1,
            nodata=None,
            dtype=np_values.dtype,
            crs='EPSG:25832',
            transform=transform,
    ) as dataset:
        dataset.write(np_values, 1)
        dataset.close()

    return file_path


# uses the result as geotif and a geodataframe to clip the results to the area of interest
def clip_geotif_with_geodf(tif_path, gdfs_to_clip_to: List[geopandas.GeoDataFrame]):
    xds = rioxarray.open_rasterio(tif_path)

    try:
        for gdf in gdfs_to_clip_to:
            if isinstance(gdf, geopandas.GeoDataFrame):
                xds = xds.rio.clip(gdf.geometry, gdf.crs, drop=True, invert=False)

        xds.rio.to_raster(tif_path, tiled=True, dtype="float32")  # save new geotif

    except NoRioDataException as e:
        # clip throws exception if data and roi do not overlap.
        # return no data in that case.

        # Todo: replace tif with empty tif
        return []

    # ensure right shape for result
    data = xds.data
    while (len(np.array(data).shape)) > 2:
        # sometimes the dataset gets wrapped into an extra dimension
        data = data[0]

    return data.tolist()

# returns coords of bounding box
# BoundingBox(left=358485.0, bottom=4028985.0, right=590415.0, top=4265115.0)
def get_bounds_for_geotif(tif_path):
    dataset = rasterio.open(tif_path)

    return dataset.bounds


# converts tif to geojson and returns feature array
def convert_tif_to_geojson(tif_path) -> List[dict]:
    features = []
    dataset = rasterio.open(tif_path)
    # Read the dataset's valid data mask as a ndarray.
    mask = dataset.read(1)

    # Extract feature shapes and values from the array.
    for geom, val in rasterio.features.shapes(
            mask, transform=dataset.transform):

        if math.isnan(val):
            # ignore no values
            continue

        feature = {
            "type": "Feature",
            "geometry": geom,
            "properties": {"value": round(val, 1)}
        }
        # append feature to geojson
        features.append(feature)

    # Use Geopandas to reproject all features to EPSG:4326
    # geopandas also automatically merges all polygons with same values
    gdf = geopandas.GeoDataFrame.from_features(features, crs="urn:ogc:def:crs:EPSG::25832",
                                               columns=["geometry", "value"])
    gdf = gdf.to_crs("EPSG:4326")
    reprojected_features_geojson = json.loads(gdf.to_json(na='null', show_bbox=False))  # features in geojson format

    return reprojected_features_geojson


# gets a values from a nested object
def get_value(data, path):
    for prop in path:
        if len(prop) == 0:
            continue
        if prop.isdigit():
            prop = int(prop)
        data = data[prop]
    return data


# get size of the bbox (assuming squares)
def get_bbox_size(bbox):
    x_cooords = bbox.exterior.xy[0]

    return max(x_cooords) - min(x_cooords)


# takes and array of geojsons and merges them into one
def summarize_multiple_geojsons_to_one(geojson_array):
    # combine array of geojson to 1 geojson
    all_features = []
    for result in geojson_array:
        all_features.extend(result["features"])
    
    results_gdf = geopandas.GeoDataFrame.from_features(
        all_features,
        crs="EPSG:4326",
        columns=list(all_features[0]["properties"].keys()) + ["geometry"]
    )
    
    # dissolve polygons with the same value in the "value" column
    results_gdf.dissolve(by='value')
    
    return json.loads(results_gdf.to_json())