from shapely.geometry import Polygon

from wind.cityPyo import CityPyo
from wind.wind_scenario_params import WindScenarioParams
from wind.data import init_bbox_matrix_for_project_area, get_buildings_for_bbox, init_bbox_matrix_for_project_area
from wind.infrared_user import InfraredUser
from wind.infrared_project import InfraredProject


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


def create_infrared_user_from_json(infrared_user_json):
    # locally recreate InfraredUser, to handle communication with the Infrared endpoint
    return InfraredUser(
        reset_user_at_endpoint=False,
        uuid = infrared_user_json["uuid"],
        token = infrared_user_json["token"]
    )
    

def create_infrared_project_from_json(infrared_project_json):
    # locally recreate InfraredUser, to handle communication with the Infrared endpoint
    infrared_user = create_infrared_user_from_json(
        {
            "uuid": infrared_project_json["infrared_client"]["uuid"],        
            "token": infrared_project_json["infrared_client"]["token"]
        }
    )
        
    # locally recreate infrared project, in order to use result formatting logic
    infrared_project = InfraredProject(
            infrared_user, 
            infrared_project_json["name"], 
            Polygon(infrared_project_json["bbox_coords"]),
            infrared_project_json["resolution"],
            infrared_project_json["buffer"],
            infrared_project_json["snapshot_uuid"]
            )

    return infrared_project

# divides the Grasbrook area into several result tiles (bboxes)
def get_grasbrook_bboxes() -> list:
    return init_bbox_matrix_for_project_area(bbox_size)


# creates a infrared project at the AIT endpoint for a bbox
def create_infrared_project_for_bbox_and_user(infrared_user_json: dict, user_id: str, bbox_coords: list, bbox_id: str) -> dict:
    infrared_user = create_infrared_user_from_json(infrared_user_json)
    
    print(user_id, bbox_id)
    
    project = {
       "projectName": user_id + "_" + str(bbox_id),
       "bbox": Polygon(bbox_coords),
    }
    # create missing projects at AIT endpoint
    infrared_project = InfraredProject(infrared_user, project["projectName"], project["bbox"], analysis_resolution, bbox_buffer)
           
    return infrared_project.export_to_json()


# trigger calculation at AIT endpoint for a infrared_project with given scenario settings and buildings
def start_calculation_for_project(scenario, buildings, infrared_project_json):
    infrared_project = create_infrared_project_from_json(infrared_project_json)
    scenario = WindScenarioParams(scenario)
    
    print("preparing inputs for project %s" %infrared_project.name)
    # prepare inputs
    # TODO update_buildings_for_infrared_project(infrared_project, buildings)

    return infrared_project.trigger_calculation_at_endpoint_for(scenario)


# collects the result of a triggered calculation
def collect_result_for_project(result_uuid: str, infrared_project_json: dict):
    infrared_project = create_infrared_project_from_json(infrared_project_json)

    # download and return result
    return {
        "raw_result": infrared_project.download_result_and_crop_to_roi(result_uuid),
        "infrared_project_json": infrared_project_json
    }


