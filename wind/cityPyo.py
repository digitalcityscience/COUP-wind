import time
import datetime
import warnings

import requests
import os
import json

import geopandas as gpd
from shapely import wkb


cwd = os.getcwd()


class CityPyo:
    """Class to handle CityPyo communication and users
        - Logs in all users listed in config and saves their user ids.
        - Gets data from cityPyo
        - Posts data to cityPyo
    """
    def __init__(self):
        self.url = os.getenv("CITY_PYO")


    def get_buildings_for_user(self, user_id):
        try:
            # prioritize a buildings.json
            buildings_json = self.get_layer_for_user(user_id, "buildings")
        except:
            buildings_json = self.get_layer_for_user(user_id, "upperfloor")
        
        # DROP Z VALUES IN GEOMETRY IF EXISTS
        df = gpd.GeoDataFrame.from_features(buildings_json["features"])

        def _drop_z(geom):
            return wkb.loads(wkb.dumps(geom, output_dimension=2))

        df.geometry = df.geometry.transform(_drop_z)

        return json.loads(df.to_json())


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


    # logs a the performance of a AIT-calculation request to CityPyo
    def log_calculation_request(self, calc_type: str, result_uuid: str):
        request_time = str(datetime.datetime.now())

        data = { 
            "timestamp": request_time,
            "result_uuid": result_uuid,
            "calc_type": calc_type,
            "target_url": os.getenv("INFRARED_URL")
        }

        request_url = self.url +  "logCalcRequestAIT/"

        try:
            request = requests.post(request_url, json=data)
        except:
            warnings.warn("Could not log calculation request to CityPyo")
            return

        if not request.status_code == 200:
            warnings.warn("Could not log AIT request", data)




