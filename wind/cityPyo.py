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
        self.url = os.getenv("CITY_PYO")


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

