import requests
import json
import os
import time

from shapely.ops import transform
from shapely.geometry import Polygon
from icecream import ic
import asyncio

from wind.data import export_result_to_geotif, clip_geotif_with_geodf, get_south_west_corner_coords_of_bbox, \
    get_bounds_for_geotif, transformer_to_wgs

import wind.queries


cwd = os.getcwd()
config = None


# TODO move to own file
class InfraredUser:
    """Class to handle Infrared communication for the InfraredUser"""

    def __init__(self, reset_user_at_endpoint=False, uuid=None, token=None):
        self.uuid = uuid
        self.token = token

        if not self.uuid:
            self.infrared_user_login()

        if reset_user_at_endpoint:
            self.delete_all_projects()

        self.all_projects = self.get_all_projects()

    # logs in infrared user
    def infrared_user_login(self):
        user_creds = {"username": os.getenv("INFRARED_USERNAME"), "password": os.getenv("INFRARED_PASSWORD")}
        request = requests.post(os.getenv("INFRARED_URL"), json=user_creds)

        if request.status_code == 200:
            # get the auth token from the returned cookie
            print(request.cookies)
            self.uuid = request.cookies.get("InFraReDClientUuid")
            self.token = "InFraReD=" + request.cookies.get("InFraReD")
        else:
            raise Exception("Failed to login to infrared by returning code of {}".format(request.status_code))
    
    def export_to_json(self):
        return {
            "uuid": self.uuid,
            "token": self.token,
        }
    # deletes all projects for the infrared user
    def delete_all_projects(self):
        for project_uuid in self.get_projects_uuids():
            print(project_uuid, "deleted")
            make_query(wind.queries.delete_project_query(self.uuid, project_uuid), self.token)

    # deletes all projects belonging to a city_pyo_user
    def delete_all_projects_for_city_pyo_user(self, city_pyo_user):
        for project_uuid, project in self.all_projects.items():
            if city_pyo_user in  project["projectName"]:
                print(project_uuid, "deleted")
                make_query(wind.queries.delete_project_query(self.uuid, project_uuid), self.token)

        # update all projects variable
        self.all_projects = self.get_all_projects() 


    # gets all the user's projects
    def get_all_projects(self):
        all_projects = make_query(wind.queries.get_projects_query(self.uuid), self.token)

        try:
            projects = get_value(
                all_projects,
                ["data", "getProjectsByUserUuid", "infraredSchema", "clients", self.uuid, "projects"]
            )
        except KeyError:
            print("no projects for user")
            return {}

        return projects

    # gets all the user's projects
    def get_projects_uuids(self):
        all_projects = self.get_all_projects()

        return all_projects.keys()

    # the root snapshot of the infrared project will be used to create buildings and perform analysis
    def get_root_snapshot_id_for_project_uuid(self, project_uuid):
        graph_snapshots_path = ["data", "getSnapshotsByProjectUuid", "infraredSchema", "clients", self.uuid,
                                "projects", project_uuid, "snapshots"]
        snapshot = make_query(wind.queries.get_snapshot_query(project_uuid), self.token)

        snapshot_uuid = list(get_value(snapshot, graph_snapshots_path).keys())[0]

        if not snapshot_uuid:
            print("could not get snapshot uuid")
            exit()

        return snapshot_uuid

    # infrared needs any request to be performed by user at least 1 per hour to keep account alive
    def keep_alive_ping(self):
        self.get_projects_uuids()


class InfraredProject:
    def __init__(
            self,
            user: InfraredUser,
            name,
            bbox_utm: Polygon,
            resolution,
            bbox_buffer,
            snapshot_uuid=None,
            project_uuid=None,
            result_type=None
    ):
        # set properties
        self.user = user
        self.name = name
        self.project_uuid = project_uuid
        self.snapshot_uuid = snapshot_uuid
        self.result_type = result_type

        # set bbox properties

        # TODO bbox operations to data - also use in main.py
        self.bbox_utm  = bbox_utm
        self.bbbox_wgs = transform(transformer_to_wgs, bbox_utm)

        self.bbox_buffer = bbox_buffer
        self.buffered_bbox_utm = bbox_utm.buffer(bbox_buffer, cap_style=3).exterior.envelope
        self.buffered_bbox_wgs = transform(transformer_to_wgs, self.buffered_bbox_utm)

        self.analysis_grid_resolution = resolution
        self.bbox_size = get_bbox_size(self.buffered_bbox_utm)
        # self.bbox_sw_corner_utm = get_south_west_corner_coords_of_bbox(self.bbox_utm)
        self.bbox_sw_corner_wgs = get_south_west_corner_coords_of_bbox(self.buffered_bbox_wgs)

        # Placeholders
        self.gdf_result_roi = None
        self.buildings = []
        self.wind_speed = None
        self.wind_direction = None
        self.wind_result_uuid = None
        self.wind_result = None
        self.wind_result_geotif = None
        self.solar_result_geotif = None
        self.sunlight_result_geotif = None
        self.solar_result_uuid = None
        self.sunlight_result_uuid = None

        # init the project at endpoint if not existing yet
        if not project_uuid:
            self.create_new_project()
            self.get_root_snapshot_id()
            self.delete_osm_geometries()

    """Class to handle Infrared communication for a InfraredProject (one bbox to analyze)"""

    def delete_existing_project_with_same_name(self):
        for project_uuid, project in self.user.get_all_projects().items():
            if project["projectName"] == self.name:
                print("project with name %s already exists. deleting it" % self.name)
                delete_response = make_query(wind.queries.delete_project_query(self.user.uuid, project_uuid), self.user.token)
                successfully_del = delete_response['data']['deleteProject']['success']
                print("success deleting %s" % successfully_del)


    # for now every calcuation request creates a new infrared project, as calculation bbox is set on project level
    def create_new_project(self):
        self.delete_existing_project_with_same_name()
        
        # create new project
        query = wind.queries.create_project_query(self.user.uuid,
                                             self.name,
                                             self.bbox_sw_corner_wgs[0],
                                             self.bbox_sw_corner_wgs[1],
                                             self.bbox_size,
                                             self.analysis_grid_resolution
                                             )
        # creation of new projects sometimes fails
        try:
            new_project_response = make_query(query, self.user.token)
            successfully_created = new_project_response['data']['createNewProject']['success']
            project_uuid = get_value(new_project_response, ["data", "createNewProject", "uuid"])
            self.project_uuid = project_uuid
            print("project name %s , created: %s" %(self.name, successfully_created))
        except Exception as e:
            print("could not create new project", e)
            self.create_new_project()

        if not successfully_created:
            print("project not sucessfully created name %s , %s uuid" % (self.name, self.project_uuid))
            # check if the project got initiated in the end. if not - delete it and recreate.
            time.sleep(1)
            self.create_new_project()

    # the root snapshot of the infrared project will be used to create buildings and perform analysis
    def get_root_snapshot_id(self):
        graph_snapshots_path = ["data", "getSnapshotsByProjectUuid", "infraredSchema", "clients", self.user.uuid,
                                "projects", self.project_uuid, "snapshots"]
        snapshot = make_query(wind.queries.get_snapshot_query(self.project_uuid), self.user.token)

        self.snapshot_uuid = list(get_value(snapshot, graph_snapshots_path).keys())[0]

        if not self.snapshot_uuid:
            print("could not get snapshot uuid")
            exit()

    # returns true if the bbox intersects with the roi
    def is_bbox_in_roi(self):
        return any(self.gdf_result_roi.intersects(self.bbox_utm))

    # deletes all preexisting geometries that infrared automatically creates from osm
    def delete_osm_geometries(self):
        # get all geometries in snapshot
        snapshot_geometries = make_query(
            wind.queries.get_geometry_objects_in_snapshot_query(self.snapshot_uuid),
            self.user.token
        )

        self.delete_all_buildings(snapshot_geometries)
        self.delete_all_streets(snapshot_geometries)

    def delete_all_buildings(self, snapshot_geometries):
        building_ids_path = ["data", "getSnapshotGeometryObjects", "infraredSchema", "clients", self.user.uuid,
                             "projects", self.project_uuid, "snapshots", self.snapshot_uuid, "buildings"]
        try:
            buildings_uuids = get_value(snapshot_geometries, building_ids_path).keys()
        except KeyError:
            print("no buildings in snapshot")
            return

        # delete all buildings
        for building_uuid in buildings_uuids:
            make_query(wind.queries.delete_building(self.snapshot_uuid, building_uuid), self.user.token)  # todo async

    # deletes all streets
    def delete_all_streets(self, snapshot_geometries):
        streets_ids_path = ["data", "getSnapshotGeometryObjects", "infraredSchema", "clients", self.user.uuid,
                            "projects", self.project_uuid, "snapshots", self.snapshot_uuid, "streetSegments"]
        try:
            streets_uuids = get_value(snapshot_geometries, streets_ids_path).keys()
        except:
            print("no streets in snapshot")
            return

        # delete all streets
        for street_uuid in streets_uuids:
            self.delete_street(street_uuid)  # todo async

    def delete_street(self, street_uuid):
        pass  # TODO comment in again
        # make_query(wind.queries.delete_street(self.snapshot_uuid, street_uuid), self.user.token)
        # currently streets have no effect at endpoint. ignore changes.
        # del self.streets[street_uuid]
        # self.reset_results()  # reset results after buildings changed

    # updates all buildings in bbox
    def update_buildings(self, buildings_in_bbox):
        print("updating buildings for InfraredProject %s" % self.name)
        bbox_buildings_ids = map(lambda bld: bld['city_scope_id'], buildings_in_bbox)
        self.buildings = buildings_in_bbox

        # TODO the buildings on the project do not persist. 

        # delete any removed buildings first
        buildings_to_delete = []
        for uuid, known_building in self.buildings.items():
            # delete if not in bbox at all (building was allegedly removed from bbox)
            if known_building["city_scope_id"] not in bbox_buildings_ids:
                buildings_to_delete.append(uuid)
        for uuid in buildings_to_delete:
            self.delete_building(uuid)

        buildings_to_delete = []
        buildings_to_create = []
        # add or update buildings in bbox if changed
        for city_io_bld in buildings_in_bbox:
            if city_io_bld in self.buildings.values():
                # building already exists and did not update
                continue

            # clean up existing buildings
            for uuid, known_building in self.buildings.items():
                # delete known building that had been updated
                if known_building["city_scope_id"] == city_io_bld["city_scope_id"]:
                    buildings_to_delete.append(uuid)

            # create new building
            buildings_to_create.append(city_io_bld)
        
        #print("buildings to delete", buildings_to_delete)
        #print("buildings to create", buildings_to_create)

        for uuid in buildings_to_delete:
            self.delete_building(uuid)

        for new_building in buildings_to_create:
            self.create_new_building(new_building)

    def delete_building(self, building_uuid):
        make_query(wind.queries.delete_building(self.snapshot_uuid, building_uuid), self.user.token)
        del self.buildings[building_uuid]
        self.reset_results()  # reset results after buildings changed

    def create_new_building(self, new_building):
        new_bld_response = make_query(wind.queries.create_building_query(new_building, self.snapshot_uuid), self.user.token)
        uuid = get_value(new_bld_response, ["data", "createNewBuilding", "uuid"])

        if not uuid:
            print("could not create building!")
            self.create_new_building(new_building)

        self.buildings[uuid] = new_building
        self.reset_results()  # reset results after buildings have changed

    # update wind speed and direction if necessary. reset results if they changed.
    def update_calculation_settings(self, wind_speed, direction):
        if not (wind_speed == self.wind_speed and direction == self.wind_direction):
            self.wind_speed = wind_speed
            self.wind_direction = direction
            self.reset_results()  # results are no longer valid

    # reset all saved results
    def reset_results(self):
        self.wind_result, self.wind_result_uuid = None, None
        self.solar_result, self.solar_result_uuid = None, None
        self.sunlight_result, self.sunlight_result_uuid = None, None

    def get_result_uuid_for(self, result_type):
        if result_type == "wind":
            return self.wind_result_uuid

        elif result_type == "solar":
            return self.solar_result_uuid

        elif result_type == "sunlight":
            return self.sunlight_result_uuid

        else:
            print(result_type)
            raise NotImplementedError

    def get_result_for(self, result_type):
        if result_type == "wind":
            return self.wind_result

        elif result_type == "solar":
            return self.solar_result

        elif result_type == "sunlight":
            return self.sunlight_result

        else:
            print(result_type)
            raise NotImplementedError

    def set_result_uuid_for(self, result_type, uuid):
        if result_type == "wind":
            self.wind_result_uuid = uuid

        elif result_type == "solar":
            self.solar_result_uuid = uuid

        elif result_type == "sunlight":
            self.sunlight_result_uuid = uuid

        else:
            print(result_type)
            raise NotImplementedError

    def set_result_for(self, result_type, result):
        if not result:
            result = {"analysisOutputData": []}

        if result_type == "wind":
            self.wind_result = result
            return

        elif result_type == "solar":
            self.solar_result = result

        elif result_type == "sunlight":
            self.sunlight_result = result

        else:
            print(result_type)
            raise NotImplementedError

    def get_result_geotif_for(self, result_type):
        if result_type == "wind":
            return self.wind_result_geotif

        elif result_type == "solar":
            return self.solar_result_geotif

        elif result_type == "sunlight":
            return self.sunlight_result_geotif

        else:
            print(result_type)
            raise NotImplementedError


    def set_result_geotif_for(self, result_type, geo_tif_path):
        if result_type == "wind":
            self.wind_result_geotif = geo_tif_path

        elif result_type == "solar":
            self.solar_result_geotif = geo_tif_path

        elif result_type == "sunlight":
            self.sunlight_result_geotif = geo_tif_path

        else:
            print(result_type)
            raise NotImplementedError

    def get_solar_results(self):
        return make_query(wind.queries.run_solar_rad_service_query(self.snapshot_uuid), self.user.token)
        # solar_result_uuid = get_value(solar_results, ['data', 'runServiceSolarRadiation', 'uuid'])

    def get_sunlight_results(self):
        return make_query(wind.queries.run_sunlight_hours_service_query(self.snapshot_uuid), self.user.token)
        # sunlight_result_uuid = get_value(sunlight_results, ['data', 'runServiceSunlightHours', 'uuid'])

    def trigger_calculation_at_endpoint_for(self, result_type):
        self.set_result_for(result_type, None)  # reset current result

        query = None

        if result_type == "wind":
            query = wind.queries.run_cfd_service_query(self.wind_direction, self.wind_speed, self.snapshot_uuid)
            service_command = 'runServiceWindComfort'

        if result_type == "solar":
            query = wind.queries.run_solar_rad_service_query(self.snapshot_uuid)
            service_command = 'runServiceSolarRadiation'

        if result_type == "sunlight":
            query = wind.queries.run_sunlight_hours_service_query(self.snapshot_uuid)
            service_command = 'runServiceSunlightHours'

        # make query to trigger result calculation on endpoint
        try:
            res = make_query(query, self.user.token)
            result_uuid = get_value(res, ['data', service_command, 'uuid'])
            # TODO delete ? self.set_result_uuid_for(result_type, get_value(res, ['data', service_command, 'uuid']))

            return result_uuid
        except Exception as exception:
            print("calculation for ", result_type, " FAILS")
            print(exception)

    # waits for the result to be avaible. Then crops it to the area of interest.
    def download_result_and_crop_to_roi(self, result_uuid, result_type="wind") -> dict: # TODO get rid of result type
        tries = 0
        max_tries = 100
        response = make_query(wind.queries.get_analysis_output_query(result_uuid, self.snapshot_uuid), self.user.token)

        # wait for result to arrive
        while (not get_value(response, ["data", "getAnalysisOutput", "infraredSchema"])) and tries <= max_tries:
            tries += 1
            response = make_query(wind.queries.get_analysis_output_query(result_uuid, self.snapshot_uuid), self.user.token)
            time.sleep(2)  # give the API some time to calc something

        if not tries > max_tries:
            result = get_value(
                response, ["data", "getAnalysisOutput", "infraredSchema", "clients", self.user.uuid,
                           "projects", self.project_uuid, "snapshots", self.snapshot_uuid, "analysisOutputs",
                           result_uuid]
            )

            # update result, after cropping to roi
            self.crop_result_data_to_roi(result, result_type)
            self.set_result_for(result_type, result)
            return result
        else:
            self.set_result_for(result_type, None)
            return {}

    # private
    def crop_result_data_to_roi(self, result, result_type):
        if self.buffered_bbox_utm is not self.bbox_utm:  # bbox is buffered
            import geopandas
            # create a tif with the buffered bbox containing all data.
            geo_tif_path = self.save_result_as_geotif(result, result_type, self.buffered_bbox_utm)  # export as tif, so it can be cropped
            # create a gdf of the unbuffered bbox. To clip to this.
            bbox_gdf = geopandas.GeoDataFrame([self.bbox_utm], columns=["geometry"])
            # clip the result twice: Remove buffer from bbox, then clip to roi
            result["analysisOutputData"] = clip_geotif_with_geodf(geo_tif_path, [bbox_gdf, self.gdf_result_roi])

        else:  # bbox is not buffered
            # export as tif, so it can be cropped
            geo_tif_path = self.save_result_as_geotif(result, result_type, self.bbox_utm)
            # BBOX is not buffered. No need to remove buffer
            result["analysisOutputData"] = clip_geotif_with_geodf(geo_tif_path, [self.gdf_result_roi])


    # TODO private
    def save_result_as_geotif(self, result, result_type, bbox):
        # save result as geotif so it can be easily cropped to roi
        geo_tif_path = export_result_to_geotif(result["analysisOutputData"], bbox, self.name, result_type)
        self.set_result_geotif_for(result_type, geo_tif_path)

        return geo_tif_path


    def get_bounds_of_geotif_bounds(self, result_type, projection='utm'):
        import rasterio
        dataset = rasterio.open(self.get_result_geotif_for(result_type))

        # BoundingBox(left=358485.0, bottom=4028985.0, right=590415.0, top=4265115.0)
        left, bottom, right, top = get_bounds_for_geotif(self.get_result_geotif_for(result_type))
        boundsPoly = Polygon([
            [left, bottom],
            [right, bottom],
            [right, top],
            [left, top],
            [left, bottom]
        ]
        )

        if projection == "utm":
            return boundsPoly

        if projection == "wgs":
            return transform(transformer_to_wgs, boundsPoly)

        raise NotImplementedError


# make query to infrared api
def make_query(query, token_cookie):
    """
        Make query response
        auth token needs to be send as cookie
    """
    # print(query)

    # AIT requested a sleep between the requests. To let their servers breath a bit.
    # time.sleep(0.5)

    request = requests.post(os.getenv("INFRARED_URL") + '/api', json={'query': query}, headers={'Cookie': token_cookie, 'origin': os.getenv('INFRARED_URL')})
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Query failed to run by returning code of {}. {}".format(request.status_code, query))


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


if __name__ == '__main__':
    mock_request_data = {
        "scenario_hash": "123yxz",
        "analysis_grid_resolution": 10,
        "south_west_latitude": 53.53189166824669,
        "south_west_longitude": 10.014580708956348,
        "latitude_delta_m": 500,
        "longitude_delta_m": 500,
    }
