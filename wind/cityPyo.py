import time

import requests
import json
import os

from wind.data import make_gdf_from_geojson

cwd = os.getcwd()


class CityPyo:
    """Class to handle CityPyo communication and users
        - Logs in all users listed in config and saves their user ids.
        - Gets data from cityPyo
        - Posts data to cityPyo
    """
    def __init__(self):
        with open(cwd + "/wind/" + "cityPyo.json") as f:
            self.config = json.load(f)

        self.url = self.config["url"]
        self.cityPyo_users = self.config["users"]
        self.cityPyo_user_ids = []
        self.known_scenario_hashes = {}
        self.last_known_buildings = {}

        # login in each user to obtain user id
        for user_credentials in self.cityPyo_users:
            try:
                # get user id trough authentication to cityPyo
                user_id = self.login_and_get_user_id(user_credentials)
                # append id to user ids
                self.cityPyo_user_ids.append(user_id)
                # init scenario hash storage
                self.known_scenario_hashes[user_id] = {}
                self.last_known_buildings[user_id] = self.get_buildings_gdf_for_user(user_id)
            except Exception as e:
                print("Could not login user to cityPyo", user_credentials)
                print("cityPyo url ", self.url)
                print("Exception ", e)
                exit()

    # login to cityPyo using the local user_cred_file
    # saves the user_id as global variable
    def login_and_get_user_id(self, user_cred):
        print("login in to cityPyo")
        response = requests.post(self.url + "login", json=user_cred)

        return response.json()['user_id']

    def get_scenarios_for_user_id(self, user_id):
        return self.get_layer_for_user(user_id, "wind_scenario")

    def get_buildings_gdf_for_user(self, user_id):
        try:
            # prioritize a buildings.json
            return make_gdf_from_geojson(self.get_layer_for_user(user_id, "buildings"))
        except:
            return make_gdf_from_geojson(self.get_layer_for_user(user_id, "upperfloor"))

    def get_layer_for_user(self, user_id, layer_name, recursive_iteration=0):
        data = {
            "userid": user_id,
            "layer": layer_name
        }

        try:
            response = requests.get(self.url + "getLayer", json=data)

            if not response.status_code == 200:
                print("could not get from cityPyo")
                print("wanted to get layer: ", layer_name)
                print("Error code", response.status_code)
                # todo raise error and return error
                return {}
        # exit on request exception (cityIO down)
        except requests.exceptions.RequestException as e:
            print("CityPyo error. " + str(e))

            if recursive_iteration > 10:
                raise requests.exceptions.RequestException

            time.sleep(30 * recursive_iteration)
            recursive_iteration += 1

            return self.get_layer_for_user(user_id, layer_name, recursive_iteration)

        return response.json()

    def add_scenario_to_known_scenarios(self, user_id, scenario_id, scenario_hash):
        try:
            self.known_scenario_hashes[user_id][scenario_id].append(scenario_hash)
        except KeyError:
            # no result hash known for scenario_id. Add the first.
            self.known_scenario_hashes[user_id][scenario_id] = []
            self.known_scenario_hashes[user_id][scenario_id].append(scenario_hash)


    # TODO known layers handling can be deleted
    def is_scenario_known(self, user_id, scenario_id, scenario_hash):
        try:
            if scenario_hash in self.known_scenario_hashes[user_id][scenario_id]:
                return True
        # no result hash known for scenario_id.
        except KeyError:
            pass

        # try to fetch results from cityPyo (might be there but not saved in local variable, due to newstart)
        if self.get_layer_for_user(user_id, "wind_" + scenario_hash):
            # add to known layers
            # TODO known layers handling can be deleted
            self.add_scenario_to_known_scenarios(user_id, scenario_id, scenario_hash)
            return True

        return False

    def post_results(self, cityPyo_user, scenario_hash, results, result_type, result_format, results_complete):
        if result_format == "raw" or result_format == "geotiff" or result_format == "png":
            self.post(cityPyo_user, scenario_hash, {"complete": results_complete, "results": results}, result_type)

        elif result_format == "geojson":
            geojson = {
                    "type": "FeatureCollection",
                    "name": "mask_bbox",
                    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
                    "features": [result for result in results]
            }
            self.post(cityPyo_user, scenario_hash, {"complete": results_complete, "results": geojson}, result_type)

        else:
            raise NotImplementedError

    def post(self, user_id, scenario_hash, payload, result_type, nested_keys=None):
        if nested_keys is None:
            nested_keys = []
        print("\n sending to cityPyo")

        try:
            query = result_type + '_' + scenario_hash   # todo replace with result type (wind, sun, solar)
            if nested_keys:
                for nested_key in nested_keys:
                    query += "/" + nested_key

            data = {
                "userid": user_id,
                "data": payload
            }
            response = requests.post(self.url + "addLayerData/" + query, json=data)

            if not response.status_code == 200:
                print("could not post to cityPyo")
                print("Error code", response.status_code)
            else:
                print("\n")
                print("result send to cityPyo.", "Result type and hash: ", result_type, ", ", scenario_hash)
            # exit on request exception (cityIO down)
        except requests.exceptions.RequestException as e:
            print("CityPyo error. " + str(e))

    # checks wether the buildings were updated at endpoint
    # TODO consider using a hash at endpoint side, so we dont have to send 2mb every second
    # todo use redis database to store data and compare with that.
    def were_buildings_updated(self, user_id) -> bool:
        buildings_at_endpoint = self.get_buildings_gdf_for_user(user_id)

        print("buildigns at endpoint", buildings_at_endpoint.head())
        print(self.last_known_buildings[user_id].head())

        if buildings_at_endpoint.equals(self.last_known_buildings[user_id]):
            # buidlings did not change. Return false
            return False

        # update known buildings, return true
        self.last_known_buildings[user_id] = buildings_at_endpoint
        return True

