from attr.setters import convert
from shapely.geometry import Polygon

from wind.cityPyo import CityPyo
from wind.data import convert_tif_to_geojson, init_bbox_matrix_for_project_area, get_buildings_for_bbox, init_bbox_matrix_for_project_area, make_gdf_from_geojson
from wind.infrared_user import InfraredUser
from wind.infrared_project import InfraredProject


# todo get resolution and bbox_buffer from config
max_bbox_size = 500  # max size of a cell of a Infrared project
bbox_size = 460  # length of one cell in the raster covering the project area
bbox_buffer = (max_bbox_size - bbox_size) / 2
analysis_resolution = 10  # resolution of analysis in meters

cityPyo = CityPyo()   # TODO externalize collection of buildings!


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


def create_infrared_user_from_json(infrared_user_json):
    # locally recreate InfraredUser, to handle communication with the Infrared endpoint
    return InfraredUser(
        reset_user_at_endpoint=False,
        uuid = infrared_user_json["uuid"],
        token = infrared_user_json["token"]
    )
    

def recreate_infrared_project_from_json(infrared_project_json, update_buildings=True):
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
            infrared_project_json["cityPyo_user"], 
            infrared_project_json["name"], 
            Polygon(infrared_project_json["bbox_coords"]),
            infrared_project_json["resolution"],
            infrared_project_json["buffer"],
            infrared_project_json["snapshot_uuid"],
            infrared_project_json["project_uuid"],
            update_buildings_at_endpoint=update_buildings
            )

    return infrared_project

# divides the Grasbrook area into several result tiles (bboxes)
def get_bboxes(city_pyo_user) -> list:
    return init_bbox_matrix_for_project_area(city_pyo_user, bbox_size)


# creates a infrared project at the AIT endpoint for a bbox
def create_infrared_project_for_bbox_and_user(infrared_user_json: dict, user_id: str, bbox_coords: list, bbox_id: str) -> dict:
    infrared_user = create_infrared_user_from_json(infrared_user_json)
    
    print(user_id, bbox_id)
    
    project = {
       "projectName": user_id + "_" + str(bbox_id),
       "bbox": Polygon(bbox_coords),
    }
    # create missing projects at AIT endpoint
    infrared_project = InfraredProject(
        infrared_user, 
        user_id,
        project["projectName"], 
        project["bbox"], 
        analysis_resolution, 
        bbox_buffer, 
        update_buildings_at_endpoint=True
    )
           
    return infrared_project.export_to_json()


# trigger calculation at AIT infrared endpoint for a infrared_project with given scenario settings and buildings [geojson]
def start_calculation_for_project(sim_type:str, calc_settings: dict, infrared_project_json: dict):
    # update buildings at the AIT infrared endpoint
    infrared_project = recreate_infrared_project_from_json(infrared_project_json, update_buildings=True)
    
    # then trigger calculation
    return infrared_project.trigger_calculation_at_endpoint_for(sim_type, calc_settings)


# collects the result of a triggered calculation
def collect_result_for_project(result_uuid: str, infrared_project_json: dict):
    infrared_project = recreate_infrared_project_from_json(infrared_project_json, update_buildings=False)
    # download and return result
    geojson = infrared_project.get_result(result_uuid)

    return {
        "geojson": geojson,
        "infrared_project_json": infrared_project_json
    }