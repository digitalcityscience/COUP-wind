import os
import time
import schedule

from shapely.ops import transform
from shapely.geometry import Point, Polygon

from wind.cityPyo import CityPyo
from wind.wind_scenario_params import WindScenarioParams
from wind.data import get_buildings_for_bbox, \
    get_project_area_polygons, convert_tif_to_geojson_features, get_project_area_as_gdf, make_gdf_from_coordinates, \
    make_gdf_from_geojson, get_south_west_corner_coords_of_bbox, transformer_to_wgs, transformer_to_utm, init_bbox_matrix_for_project_area
from wind.infrared import InfraredProject, InfraredUser
from wind.format_result import format_result


# todo get resolution and bbox_buffer from config
max_bbox_size = 500  # max size of a cell of a Infrared project
bbox_size = 460  # length of one cell in the raster covering the project area
bbox_buffer = (max_bbox_size - bbox_size) / 2
analysis_resolution = 10  # resolution of analysis in meters

cityPyo = CityPyo()   # TODO externalize collection of buildings!
bbox_matrix = init_bbox_matrix_for_project_area(bbox_size)  # subdivide the project area into bboxes


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


  # get the infrared projects for this city_pyo_user
def find_existing_projects_at_infrared_endpoint(infrared_user: InfraredUser, city_pyo_user):
    all_projects_at_endpoint = infrared_user.get_all_projects()
    
    if not all_projects_at_endpoint:
        return []
    
    city_pyo_user_project_names = []
    
    for project_uuid, project in all_projects_at_endpoint.items():
        if city_pyo_user in project["projectName"]:
            city_pyo_user_project_names.append(project["projectName"])

    # endpoint has duplicate projects - sometimes it is a mess there.
    if len(city_pyo_user_project_names) != len(set(city_pyo_user_project_names)):
        print("duplicate projects at endpoint!, deleting all")
        infrared_user.delete_all_projects_for_city_pyo_user(city_pyo_user)
        return []

    # create array with {} of buffered boxes and their sw corners
    bboxes_and_corners_dicts = []
    for bbox in bbox_matrix:
        buffered_bbox = bbox.buffer(bbox_buffer, cap_style=3).exterior.envelope
        bboxes_and_corners_dicts.append({
            "buffered_bbox": buffered_bbox,
            "s_w_corner": Point(get_south_west_corner_coords_of_bbox(buffered_bbox))
        })

    # filter all projects at the endpoint for projects belonging to this city_pyo_user
    city_pyo_user_projects = []
    for project_uuid, project in all_projects_at_endpoint.items():
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
    
    print("user has %s projects at infrared endpoint" % len(city_pyo_user_projects))
    print("project names and uuids")
    for project in city_pyo_user_projects:
        print("name %s , uuid %s" %(project["projectName"], project["project_uuid"]))
    
    return city_pyo_user_projects


def create_local_project_instances(infrared_user: InfraredUser, city_pyo_user: str, existing_projects: list):
    # recreate local InfraredProject instances of projects already established at endpoint
    infrared_projects_for_user = []

    # existing projects seem to match bbox matrix
    if len(existing_projects) == len(bbox_matrix):
        for project in existing_projects:
            infrared_projects_for_user.append(InfraredProject(
                infrared_user, project["projectName"], project["bbox"], analysis_resolution, bbox_buffer, project["snapshot_uuid"], project["project_uuid"]
                )
            )
        
        return infrared_projects_for_user
    
    # projects at the Infrared endpoint do not match bbox matrix - create one for each bbox.
    else:
        infrared_user.delete_all_projects_for_city_pyo_user(city_pyo_user)

        for index, bbox in enumerate(bbox_matrix):
            project = {
                "projectName": city_pyo_user + "_" + str(index),
                "bbox": bbox,
            }
            # create missing projects at AIT endpoint
            infrared_project = InfraredProject(infrared_user, project["projectName"], project["bbox"], analysis_resolution, bbox_buffer)
            infrared_projects_for_user.append(infrared_project)    

    
        return infrared_projects_for_user


def infrared_project_to_json(infrared_project: InfraredProject, result_type: str):
    return {
        "name": infrared_project.name,
        "bbox_coords": list(infrared_project.bbox_utm.exterior.coords),
        "resolution": infrared_project.analysis_grid_resolution,
        "buffer": infrared_project.bbox_buffer,
        "snapshot_uuid": infrared_project.snapshot_uuid,
        "project_uuid": infrared_project.project_uuid,
        "snapshot_uuid": infrared_project.snapshot_uuid,
        "result_type": result_type,
        "result_uuid": infrared_project.get_result_uuid_for(result_type),
        "infrared_client": {
            "uuid": infrared_project.user.uuid,
            "token": infrared_project.user.token,
        }
    }

# prepares data and requests a calculation at Infrared endpointt
def start_calculation(scenario: WindScenarioParams, result_type):
    
    print("length of bbox matrix is %s " % len(bbox_matrix))

    # init InfraredUser class to handle communication with AIT api
    infrared_user = InfraredUser()

    city_pyo_user_id = scenario.city_pyo_user_id

    # get infrared projects for cityPyoUser from AIT endpoint
    existing_projects_at_AIT = find_existing_projects_at_infrared_endpoint(infrared_user, city_pyo_user_id)
    infrared_projects = create_local_project_instances(infrared_user, city_pyo_user_id, existing_projects_at_AIT)

    # update buildings in all projects, if buildings have changed
    # todo find out if buildings were updated via redis database, update buildings at endpoint if necessary.

    # todo refactor result roi later , currently not working
    # result_roi = get_result_roi(scenario)  # geodataframe with the Area of Interest for the result

    for infrared_project in infrared_projects:
        print("preparing inputs for project %s" %infrared_project.name)
        # prepare inputs
        update_calculation_settings_for_infrared_project(scenario, infrared_project)
        # TODO update_buildings_for_infrared_project(infrared_project, cityPyo.get_buildings_gdf_for_user(city_pyo_user_id))

        # calculate results
        if not infrared_project.get_result_uuid_for(result_type):
            # triggers new wind calculation for project on endpoint. Results are collected later.
            infrared_project.trigger_calculation_at_endpoint_for(result_type)
    
    
    # return serializable info, so that the InfraredProjects can be recreated for result collection in another thread.
    return [infrared_project_to_json(project, result_type) for project in infrared_projects]
  

# collects result of 1 infrared project from AIT api, returns it after formatting
def collect_and_format_result_from_ait(infrared_project_json: dict, result_format: str, result_type="wind"):
    
    # locally recreate InfraredUser, to handle communication with the Infrared endpoint
    infrared_user = InfraredUser(
        reset_user_at_endpoint=False,
        uuid = infrared_project_json["infrared_client"]["uuid"],
        token = infrared_project_json["infrared_client"]["token"]
    )

    # locally recreate infrared project, in order to use result formatting logic
    infrared_project = InfraredProject(
            infrared_user, 
            infrared_project_json["name"], 
            Polygon(infrared_project_json["bbox_coords"]),
            infrared_project_json["resolution"],
            infrared_project_json["buffer"],
            infrared_project_json["snapshot_uuid"],
            infrared_project_json["project_uuid"],
            infrared_project_json["result_type"],
            )
    
    # download result
    infrared_project.download_result_and_crop_to_roi(result_type, infrared_project_json["result_uuid"])

    # formats result (as png, geojson, ...) before returning it
    return format_result(infrared_project, result_type, result_format)


