import json
import hashlib
import re
import time

from celery.result import GroupResult
from mycelery import app as celery_app


import wind.cityPyo as cp
from wind.wind_scenario_params import ScenarioParams
from wind.infrared_user import InfraredUser

cityPyo = cp.CityPyo() ## put cityPyo container here



def get_infrared_projects_from_group_task(group_task) -> list:
    result = group_task.get()
    group_result = GroupResult.restore(result, app=celery_app)
    
    # once the endpoint is setup the infrared projects should be served from cache
    while not group_result.ready():
        print("waiting for infrared projects to be setup")
        time.sleep(2)
    
    infrared_projects = [result.get() for result in group_result.results]

    return infrared_projects


def check_infrared_projects_still_exist(infrared_projects) -> bool:
    if not infrared_projects:
        # make sure to check valid list
        return False
    
    infrared_user = InfraredUser(
        reset_user_at_endpoint=False,
        uuid=infrared_projects[0]["infrared_client"]["uuid"],
        token=infrared_projects[0]["infrared_client"]["token"]
    )

    all_projects_uuids = infrared_user.get_projects_uuids()
    for project in infrared_projects:
        if not project["project_uuid"] in list(all_projects_uuids):
            print(f'Missing project {project["project_uuid"]} in list {list(all_projects_uuids)}')
            return False
    
    return True


def get_calculation_input(complex_task):
    # hash noise scenario settings
    wind_params = ScenarioParams(complex_task, "wind")  # TODO get "wind" from endpoint!
    calculation_settings = wind_params.export_to_json()
    scenario_hash = hash_dict(calculation_settings)

    # hash buildings geojson
    buildings = get_buildings_geojson_from_cityPyo(complex_task["city_pyo_user"])
    buildings_hash = hash_dict(buildings)

    return scenario_hash, buildings_hash, calculation_settings, buildings


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

def get_cache_key_compute_task(**kwargs):
    return kwargs["scenario_hash"] + "_" + kwargs["buildings_hash"]

def get_cache_key_setup_task(**kwargs):
    return "infrared_projects" + "_" + kwargs["city_pyo_user"]

