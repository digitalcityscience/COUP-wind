import requests
import os
import time

from shapely.ops import transform
from shapely.geometry import Polygon

from wind.data import export_result_to_geotif, clip_geotif_with_geodf, get_south_west_corner_coords_of_bbox, \
    get_bounds_for_geotif, transformer_to_wgs

import wind.queries
from wind.infrared_user import InfraredUser

cwd = os.getcwd()
config = None

"""Class to handle Infrared communication for a InfraredProject (one bbox to analyze)"""
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
        self.bbox_utm  = bbox_utm
        self.bbbox_wgs = transform(transformer_to_wgs, bbox_utm)

        self.bbox_buffer = bbox_buffer
        self.buffered_bbox_utm = bbox_utm.buffer(bbox_buffer, cap_style=3).exterior.envelope
        self.buffered_bbox_wgs = transform(transformer_to_wgs, self.buffered_bbox_utm)

        self.analysis_grid_resolution = resolution
        self.bbox_size = get_bbox_size(self.buffered_bbox_utm)
        self.bbox_sw_corner_wgs = get_south_west_corner_coords_of_bbox(self.buffered_bbox_wgs)

        # input placeholders
        self.buildings = []
        self.wind_speed = None
        self.wind_direction = None
        
        # result placeholders
        self.gdf_result_roi = None
        self.result_uuid = None
        self.raw_result = None
        self.result_geotif = None
        

        # init the project at endpoint if not existing yet
        if not project_uuid:
            self.create_new_project()
            self.get_root_snapshot_id()
            self.delete_osm_geometries()


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


    def delete_existing_project_with_same_name(self):
        for project_uuid, project in self.user.get_all_projects().items():
            if project["projectName"] == self.name:
                print("project with name %s already exists. deleting it" % self.name)
                delete_response = make_query(wind.queries.delete_project_query(self.user.uuid, project_uuid), self.user.token)
                successfully_del = delete_response['data']['deleteProject']['success']
                print("success deleting %s" % successfully_del)


    # exports project to json , so it can be serialized
    def export_to_json(self):
        return {
            "name": self.name,
            "bbox_coords": list(self.bbox_utm.exterior.coords),
            "resolution": self.analysis_grid_resolution,
            "buffer": self.bbox_buffer,
            "snapshot_uuid": self.snapshot_uuid,
            "project_uuid": self.project_uuid,
            "snapshot_uuid": self.snapshot_uuid,
            "infrared_client": {
                "uuid": self.user.uuid,
                "token": self.user.token,
            }
        }


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
        #  self.delete_all_streets(snapshot_geometries)  --- currently streets have no effect on results anyway

    # deletes all buildings for project on endpoint
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
        pass 
        """ currently streets have no effect on endpoint anyway 

        streets_ids_path = ["data", "getSnapshotGeometryObjects", "infraredSchema", "clients", self.user.uuid,
                            "projects", self.project_uuid, "snapshots", self.snapshot_uuid, "streetSegments"]
        try:
            streets_uuids = get_value(snapshot_geometries, streets_ids_path).keys()
        except:
            print("no streets in snapshot")
            return

        # delete all streets
        for street_uuid in streets_uuids:
            self.delete_street(street_uuid)  # todo async """

    def delete_street(self, street_uuid):
        pass
        # currently streets have no effect at endpoint. ignore changes.
        # make_query(wind.queries.delete_street(self.snapshot_uuid, street_uuid), self.user.token)
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



    def trigger_calculation_at_endpoint_for(self, scenario):

        query = None

        if scenario.result_type == "wind":
            query = wind.queries.run_cfd_service_query(scenario.wind_direction, scenario.wind_speed, self.snapshot_uuid)
            service_command = 'runServiceWindComfort'

        if scenario.result_type == "solar":
            query = wind.queries.run_solar_rad_service_query(self.snapshot_uuid)
            service_command = 'runServiceSolarRadiation'

        if scenario.result_type == "sunlight":
            query = wind.queries.run_sunlight_hours_service_query(self.snapshot_uuid)
            service_command = 'runServiceSunlightHours'

        # make query to trigger result calculation on endpoint
        try:
            res = make_query(query, self.user.token)
            result_uuid = get_value(res, ['data', service_command, 'uuid'])
            
            return result_uuid

        except Exception as exception:
            print("calculation for ", scenario, " FAILS")
            print(exception)


    # waits for the result to be avaible. Then crops it to the area of interest.
    def download_result_and_crop_to_roi(self, result_uuid) -> dict:
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
            self.crop_result_data_to_roi(result)
            return result
        else:
            return {}

    # private
    def crop_result_data_to_roi(self, result):
        if self.buffered_bbox_utm is not self.bbox_utm:  # bbox is buffered
            import geopandas
            # create a tif with the buffered bbox containing all data.
            geo_tif_path = self.save_result_as_geotif(result, self.buffered_bbox_utm)  # export as tif, so it can be cropped
            # create a gdf of the unbuffered bbox. To clip to this.
            bbox_gdf = geopandas.GeoDataFrame([self.bbox_utm], columns=["geometry"])
            # clip the result twice: Remove buffer from bbox, then clip to roi
            result["analysisOutputData"] = clip_geotif_with_geodf(geo_tif_path, [bbox_gdf, self.gdf_result_roi])

        else:  # bbox is not buffered
            # export as tif, so it can be cropped
            geo_tif_path = self.save_result_as_geotif(result, self.bbox_utm)
            # BBOX is not buffered. No need to remove buffer
            result["analysisOutputData"] = clip_geotif_with_geodf(geo_tif_path, [self.gdf_result_roi])


    # TODO private
    def save_result_as_geotif(self, result, bbox):
        # save result as geotif so it can be easily cropped to roi
        geo_tif_path = export_result_to_geotif(result["analysisOutputData"], bbox, self.name)
        self.result_geotif = geo_tif_path
        
        return geo_tif_path


    def get_bounds_of_geotif_bounds(self, result_type, projection='utm'):
        import rasterio
        dataset = rasterio.open(self.result_geotif)

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