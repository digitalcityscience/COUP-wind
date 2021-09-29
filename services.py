import json
import hashlib
import re

import wind.cityPyo as cp
from wind.wind_scenario_params import WindScenarioParams

cityPyo = cp.CityPyo() ## put cityPyo container here


def get_calculation_input(complex_task):
    # hash noise scenario settings
    wind_params = WindScenarioParams(complex_task)
    calculation_settings = wind_params.get_calculation_settings()
    scenario_hash = hash_dict(calculation_settings)

    # hash buildings geojson
    buildings = get_buildings_geojson_from_cityPyo(complex_task["city_pyo_user"])
    buildings_hash = hash_dict(buildings)

    return scenario_hash, buildings_hash, calculation_settings, buildings


def get_calculation_settings(scenario):
    print("scenario", scenario)
    wind_params = WindScenarioParams(scenario)

    return wind_params.get_calculation_settings()


def get_buildings_geojson_from_cityPyo(cityPyo_user_id):
    return cityPyo.get_buildings_for_user(cityPyo_user_id)


def hash_dict(dict_to_hash):
    dict_string = json.dumps(dict_to_hash, sort_keys=True)
    hash_buildings = hashlib.md5(dict_string.encode())

    return hash_buildings.hexdigest()

def is_valid_md5(checkme):
    if type(checkme) == str:
        if re.findall(r"([a-fA-F\d]{32})", checkme):
            return True

    return False

def get_cache_key(**kwargs):
    return kwargs["scenario_hash"] + "_" + kwargs["buildings_hash"]

