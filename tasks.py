from requests.api import request
from wind.wind_scenario_params import WindScenarioParams
from wind.main import collect_and_format_result_from_ait, collect_result_for_project, create_infrared_project_for_bbox_and_user, create_infrared_project_from_json, start_calculation, start_calculation_for_project
from wind.infrared import InfraredUser
from celery import signals, group, chain
from celery.utils.log import get_task_logger
from celery.result import GroupResult


from cache import Cache
from mycelery import app

from wind.main import start_calculation, get_grasbrook_bboxes

logger = get_task_logger(__name__)
cache = Cache()

# returns {"raw_result": {...}, "infrared_project_json": {...}}
@app.task()
def collect_infrared_result(result_uuid: str, infrared_project_json: dict) -> dict:
    # collect the result from AIT endpoint and format it
    return collect_result_for_project(result_uuid, infrared_project_json)


@app.task()
def create_infrared_project(infrared_user_json, user_id, bbox_coords, bbox_id):
    return create_infrared_project_for_bbox_and_user(infrared_user_json, user_id, bbox_coords, bbox_id)

# TODO the result of this method should be cached
@app.task()
def create_infrared_projects_for_cityPyo_user(user_id):
    
    # Check cache. If cached, return result from cache.     
    key = 'infrared_projects_' + user_id 
    group_result_id = cache.retrieve(key=key)
    if not group_result_id == {}:
        return group_result_id
    
    # else: create projects at endpoint and export as json
    bboxes = get_grasbrook_bboxes()
    infrared_user = InfraredUser()
    infrared_user_json = infrared_user.export_to_json()
    task_group = group([create_infrared_project.s(infrared_user_json, user_id, list(bbox.exterior.coords), bbox_id) for bbox_id, bbox in enumerate(bboxes)])
    group_result = task_group()
    group_result.save()
    
    return group_result.id

@app.task()
def trigger_calculation(wind_scenario, project):
    return start_calculation_for_project(wind_scenario, project)


# result of this method should be cached
@app.task()
def compute_wind_request(infrared_projects: list, request_json: dict):
    # todo, instead of WindScenario mehtod "get computation input like with noise. must be serializable."
    
    wind_scenario = WindScenarioParams(request_json)
    
    # Check cache. If cached, return result from cache.
    # TODO cache with building!
    key = wind_scenario.hash
    result = cache.retrieve(key=key)
    if not result == {}:
        print("result from cache!")
        print(result)
        return result
    
    # trigger calculation and collect result for project in infrared_projects
    # collect_result will get result of trigger_calculation as first argument
    task_group = group(
        [
            chain(
                trigger_calculation.s(request_json, project), # returns result_uuid
                collect_infrared_result.s(project)) # collect_result will result_uuid as first argument
                for project in infrared_projects
        ]
    )
    
    group_result = task_group()
    group_result.save()


    # Trigger calculation at AIT Infrared endpoint
    #infrared_projects = start_calculation(wind_scenario, "wind")
    
    # collect result for each of the infrared projects
    #result_format = wind_scenario.result_format
    #task_group = group([collect_infrared_result.s(project, result_format) for project in infrared_projects])
    #group_result = task_group()
    #group_result.save()
    
    return group_result.id


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get('state')
    args = kwargs.get('args')
    result = kwargs.get('retval')

    if state == "SUCCESS":
        try:
            # if first arg is a list of [infrared_project_json]
            # && if you can create WindScenarioParams from secnd arg of the request 
            # - then cache the result
            infrared_project = create_infrared_project_from_json(args[0][0])
            params = WindScenarioParams(args[1])
            cache.save(key=params.hash, value=result)
        
        except:
            # do not cache
            pass