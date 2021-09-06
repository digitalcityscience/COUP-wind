import os
from icecream import ic

from cityPyo import CityPyo
from data import get_buildings_for_bbox, create_bbox_matrix, \
    get_project_area_polygons, convert_tif_to_geojson_features, get_project_area_as_gdf, make_gdf_from_coordinates, \
    make_gdf_from_geojson, get_south_west_corner_coords_of_bbox
from infrared import InfraredProject, InfraredUser


# global values
cwd = os.getcwd()
max_bbox_size = 500  # max size of a cell of a Infrared project
bbox_size = 460  # length of one cell in the raster covering the project area
bbox_buffer = (max_bbox_size - bbox_size) / 2
infrared_project_instances = []
analysis_resolution = 10  # resolution of analysis in meters


# subdivides the project area into a bbox matrix
# returns an array of Shapely Polygon
def init_bbox_matrix_for_project_area():
    # get the polygons describing the project area (e.g. the Grasbrook development area)
    project_area_polygons = get_project_area_polygons()

    bbox_matrix = []
    for pol in project_area_polygons:
        # subdivide the project area into a matrix grid
        bbox_matrix.extend(create_bbox_matrix(pol, bbox_size))

    return bbox_matrix



# inits an infrared project for each bbox in bbox matrix
def init_infrared_user() -> InfraredUser:
    ic("creating default infrared projects for each cityPyo user.")
    infra_user = InfraredUser(reset_user_at_endpoint=True)  # init empty user
    bbox_matrix = init_bbox_matrix_for_project_area()
    cityPyo = CityPyo()

    for bbox_id, bbox in enumerate(bbox_matrix):
        print(bbox_id, bbox)
        # prepare default projects for each bbox for faster calculation at request
        for user_id in cityPyo.cityPyo_user_ids:
            # each cityPyo user gets it's own set of default projects at the endpoint
            # (to use custom building geometries)
            try:
                default_projects = infra_user.infrared_projects[user_id]
            except KeyError:
                # cityPyo user has no projects yet
                infra_user.infrared_projects[user_id] = []
                default_projects = infra_user.infrared_projects[user_id]

            # INIT INFRARED PROJECT
            project_name = user_id + "_" + str(bbox_id)
            default_projects.append(
                InfraredProject(infra_user, project_name, bbox, analysis_resolution, bbox_buffer)
            )

    # return the infrared user, containing all default projects and login information to the endpoint
    return infra_user






if __name__ == "__main__":
    init_infrared_user()
