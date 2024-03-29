import json
import hashlib
import re
import time

from celery.result import GroupResult
from celery_app import app as celery_app
from geojson_to_png import format_result_as_png


import wind.cityPyo as cp
from wind.infrared_user import InfraredUser

cityPyo = cp.CityPyo() ## put cityPyo container here


# gets a geojson and returns a result as png
def convert_result_to_png(geojson):
    return format_result_as_png(geojson)


def get_infrared_projects_from_group_task(group_task) -> list:
    result = group_task.get()
    group_result = GroupResult.restore(result, app=celery_app)
    
    # once the endpoint is setup the infrared projects should be served from cache
    while not group_result.ready():
        print("waiting for infrared projects to be setup")
        time.sleep(2)
    
    infrared_projects = [result.get() for result in group_result.results]

    return infrared_projects


def check_infrared_projects_still_exist_at_infrared(infrared_projects) -> bool:
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

    # every value needs to be hashable (dict, str , array, ..) for celery to work
    return calc_input_hash, buildings_hash, calc_input.export_to_json()


def get_buildings_geojson_from_cityPyo(cityPyo_user_id):
    return cityPyo.get_buildings_for_user(cityPyo_user_id)


def hash_dict(dict_to_hash):
    dict_string = json.dumps(dict_to_hash, sort_keys=True)
    hash_buildings = hashlib.md5(dict_string.encode())

    return hash_buildings.hexdigest()
def get_cache_key_compute_task(sim_type:str, buildings_hash:str, calc_settings_hash:str):
    return sim_type + "_" + buildings_hash + "_" +  calc_settings_hash

def get_cache_key_setup_task(**kwargs):
    return "infrared_projects" + "_" + kwargs["city_pyo_user"]



""" 
def is_valid_md5(checkme):
    if type(checkme) == str:
        if re.findall(r"([a-fA-F\d]{32})", checkme):
            return True

    return False
 """

