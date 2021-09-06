import os
import time
import asyncio
import schedule
import base64
from icecream import ic
from shapely.ops import transform
from shapely.geometry import Point

from wind.cityPyo import CityPyo
from wind.wind_scenario_params import WindScenarioParams


from wind.data import get_buildings_for_bbox, \
    get_project_area_polygons, convert_tif_to_geojson_features, get_project_area_as_gdf, make_gdf_from_coordinates, \
    make_gdf_from_geojson, get_south_west_corner_coords_of_bbox, transformer_to_wgs, transformer_to_utm, init_bbox_matrix_for_project_area
from wind.infrared import InfraredProject, InfraredUser



# todo get resolution and bbox_buffer from config
max_bbox_size = 500  # max size of a cell of a Infrared project
bbox_size = 460  # length of one cell in the raster covering the project area
bbox_buffer = (max_bbox_size - bbox_size) / 2
analysis_resolution = 10  # resolution of analysis in meters

cityPyo = CityPyo()   # TODO externalize collection of buildings!
bbox_matrix = init_bbox_matrix_for_project_area(bbox_size)
infrared_projects_for_user = {}


# TODO externalize
# def check_user_has_projects():
#     print("checking if user still alive")
#     global infrared_user
#     recreate = False
#
#     try:
#         project_uuids = infrared_user.get_projects_uuids()
#         if not project_uuids:
#             print("Projects were deleted.")
#             recreate = True
#     except:
#         recreate = True
#
#     if recreate:
#         # recreate infrared user
#         print("recreating infrared user. ")
#         del infrared_user
#         infrared_user = init_infrared_user()


# updates an infrared project with all relevant information for scenario (buildings, wind_direction, wind_speed)
def update_calculation_settings_for_infrared_project(scenario: WindScenarioParams, infrared_project: InfraredProject):
        # update wind_speed and direction
    infrared_project.update_calculation_settings(scenario.wind_speed, scenario.wind_direction)

   
# updates an infrared project with all relevant information for scenario (buildings, wind_direction, wind_speed)
def update_buildings_for_infrared_project(infrared_project: InfraredProject, cityPyo_buildings):
    # update buildings for each infrared project instance
    buildings_in_bbox = get_buildings_for_bbox(infrared_project.buffered_bbox_utm, cityPyo_buildings)

    infrared_project.update_buildings(buildings_in_bbox)


# TODO move to format_result.py
def format_result(infrared_project: InfraredProject, result_type: str,  out_format: str):
    result = infrared_project.get_result_for(result_type)

    if not result["analysisOutputData"]:
        # empty result (e.g. not in ROI) -> return empty list of features
        return []

    if out_format == "geojson":
        features = convert_tif_to_geojson_features(infrared_project.get_result_geotif_for(result_type))
        return features

    if out_format == 'geotiff':
        bounds_polygon = infrared_project.get_bounds_of_geotif_bounds(result_type, "wgs")
        bounds_coordinates = list(bounds_polygon.exterior.coords)

        with open(infrared_project.get_result_geotif_for(result_type), "rb") as image_file:
            base64_bytes = base64.b64encode(image_file.read())
            base64_string = base64_bytes.decode('utf-8')

        return [{
            "bbox_id": infrared_project.name,
            "bbox_sw_corner": get_south_west_corner_coords_of_bbox(bounds_polygon),
            "bbox_coordinates": bounds_coordinates,
            "image_base64_string": base64_string
        }]

    if out_format == "raw":
        bounds_polygon =  infrared_project.get_bounds_of_geotif_bounds(result_type, "wgs")
        bounds_coordinates = list(bounds_polygon.exterior.coords)

        return [{
            "bbox_id": infrared_project.name,
            "bbox_sw_corner": get_south_west_corner_coords_of_bbox(bounds_polygon),
            "bbox_coordinates": bounds_coordinates,
            "values": result["analysisOutputData"]
        }]

    if out_format == "png":
        bounds_polygon = infrared_project.get_bounds_of_geotif_bounds(result_type, "wgs")
        bounds_coordinates = list(bounds_polygon.exterior.coords)

        import numpy as np
        import math
        from io import BytesIO
        from PIL import Image

        image_data = result["analysisOutputData"]

        # convert image data to ints from 0-255 (for png)
        # set NaN as 0
        image_data = [
            [int(round(x * 255)) if not math.isnan(x) else 0 for x in image_line]
            for image_line in image_data
        ]
        # create a np array from image data
        np_values = np.array(image_data, dtype="uint8")

        # create a pillow image, save it and convert to base64 string
        im = Image.fromarray(np_values)
        output_buffer = BytesIO()
        im.save(output_buffer, format='PNG')
        byte_data = output_buffer.getvalue()
        base64_bytes = base64.b64encode(byte_data)
        base64_string = base64_bytes.decode('utf-8')

        img_width, img_height = im.size

        return [{
            "bbox_id": infrared_project.name,
            "bbox_sw_corner": get_south_west_corner_coords_of_bbox(bounds_polygon),
            "img_width": img_width,
            "img_height": img_height,
            "bbox_coordinates": bounds_coordinates,
            "image_base64_string": base64_string
        }]

    else:
        print("unknown format requested: ", out_format)
        raise NotImplementedError

  # get the infrared projects for this city_pyo_user
def find_existing_infrared_projects_for_city_pyo_user(infrared_user, city_pyo_user):
    ic("getting all projects from endpoint")
    all_city_science_projects_at_endpoint = infrared_user.get_all_projects()

    if not all_city_science_projects_at_endpoint:
        return []

    # create array with {} of buffered boxes and their sw corners
    bboxes_and_corners_dicts = []
    for bbox in bbox_matrix:
        buffered_bbox = bbox.buffer(bbox_buffer, cap_style=3).exterior.envelope
        bboxes_and_corners_dicts.append({
            "buffered_bbox": buffered_bbox,
            "s_w_corner": Point(get_south_west_corner_coords_of_bbox(buffered_bbox))
        })

    # match projects existing at AIT with bboxes in order to recreate projects locally
    city_pyo_user_projects = []
    for project_uuid, project in all_city_science_projects_at_endpoint.items():
        if city_pyo_user in project["projectName"]:
            project["project_uuid"] = project_uuid
            project["snapshot_uuid"] = infrared_user.get_root_snapshot_id_for_project_uuid(project_uuid)
            
            # match right spatial bbox to project
            project_sw_corner_long = project["projectSouthWestLongitude"] 
            project_sw_corner_lat = project["projectSouthWestLatitude"]
            project_corner = transform(transformer_to_utm, Point(project_sw_corner_long, project_sw_corner_lat))

            for bbox_dict in bboxes_and_corners_dicts:
                if bbox_dict["s_w_corner"].almost_equals(project_corner, decimal=4):
                    project["bbox"] = bbox_dict["buffered_bbox"]
                    city_pyo_user_projects.append(project)
                    break
    
    return city_pyo_user_projects


def create_local_project_instances(infrared_user: InfraredUser, city_pyo_user: str, existing_projects: list):
    # recreate local InfraredProject instances of projects already established at endpoint
    for project in existing_projects:
        infrared_projects_for_user[project["project_uuid"]] = InfraredProject(
            infrared_user, project["projectName"], project["bbox"], analysis_resolution, bbox_buffer, project["snapshot_uuid"], project["project_uuid"]
            )
    
    # if the AIT endpoints does not have a project for each bbox - create new projects locally and at endpoint.
    bboxes_matched_to_existing_bboxes = [project["bbox"] for project in existing_projects]

    if not len(bboxes_matched_to_existing_bboxes) == len(bbox_matrix):
        # create a new project for each bbox
        for index, bbox in enumerate(bbox_matrix):
            if bbox not in bboxes_matched_to_existing_bboxes:
                project = {
                    "projectName": city_pyo_user + "_" + str(index),
                    "bbox": bbox,
                }
                # create missing projects at AIT endpoint
                infrared_project = InfraredProject(infrared_user, project["projectName"], project["bbox"], analysis_resolution, bbox_buffer)
                infrared_projects_for_user[infrared_project.project_uuid] = infrared_project

    return infrared_projects_for_user


# TODO single task: start calculation: then group task to collect results individually.
def start_calculation(scenario: WindScenarioParams, result_type="wind"):
    # init InfraredUser class to handle communication with AIT api
    infrared_user = InfraredUser()
    
    city_pyo_user = scenario.city_pyo_user
    
    # get infrared projects for cityPyoUser from AIT endpoint
    existing_projects_at_AIT = find_existing_infrared_projects_for_city_pyo_user(infrared_user, city_pyo_user)
    infrared_projects = create_local_project_instances(infrared_user, city_pyo_user, existing_projects_at_AIT)

    print("infrared_projects in wind worker")
    print(infrared_projects)

    # update buildings in all projects, if buildings have changed
    # todo find out if buildings were updated via redis database, update buildings at endpoint if necessary.

    # todo refactor result roi later
    # result_roi = get_result_roi(scenario)  # geodataframe with the Area of Interest for the result

    for _uuid, infrared_project in infrared_projects.items():
        # prepare inputs
        update_calculation_settings_for_infrared_project(scenario, infrared_project)

        # calculate results
        if not infrared_project.get_result_uuid_for(result_type):
            ic("triggering calculation for ", infrared_project.name)
            # triggers new wind calculation for project on endpoint. Results are collected later.
            infrared_project.trigger_calculation_at_endpoint_for(result_type)
    
    return list(infrared_projects.keys())
  

# collects result of 1 infrared project from AIT api, returns it after formatting
# TODO do this as a task in a group task. mark result as complete when group task finished. 
# TODO combine all project results using celery.cache! 
async def collect_and_format_result_from_ait(infrared_project_uuid: str, result_format: str, result_type="wind"):
    infrared_project = infrared_projects_for_user[infrared_project_uuid]
    
    print("these are the infrared proejcts saved for the user")
    print(infrared_projects_for_user)

    print("*****")
    
    print("collecting fresult for", infrared_project_uuid)
    print("awaiting result here!!!")
    print(infrared_project)

    # async await remaining result
    if not infrared_project.get_result_uuid_for(result_type):
        await infrared_project.download_result_and_crop_to_roi(result_type)

    # format and return result
    return format_result(infrared_project, result_type, result_format)


