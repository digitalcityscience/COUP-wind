from celery import signals, group, chain
from celery.utils.log import get_task_logger
from mycelery import app
from cache import Cache

from services import check_infrared_projects_still_exist, get_cache_key_compute_task, get_cache_key_setup_task, is_valid_md5

from wind.infrared_user import InfraredUser
from wind.main import \
    get_grasbrook_bboxes, \
    create_infrared_project_for_bbox_and_user, \
    start_calculation_for_project, \
    collect_result_for_project


logger = get_task_logger(__name__)
cache = Cache()

# returns {"raw_result": {...}, "infrared_project_json": {...}}
@app.task()
def collect_infrared_result(result_uuid: str, infrared_project_json: dict) -> dict:
    # collect the result from AIT endpoint and format it
    return collect_result_for_project(result_uuid, infrared_project_json)


""" 
task to create a project at AIT endpoint
where bbox is the boundaries of the result tile
user_id is the cityPyo user_id.
"""
@app.task()
def create_infrared_project(infrared_user_json, user_id, bbox_coords, bbox_id):
    print("creating new project!!")
    return create_infrared_project_for_bbox_and_user(infrared_user_json, user_id, bbox_coords, bbox_id)


"""
creates a "infrared_project" for each result tile at the AIT endpoint
Each cityPyo user will have it's own set of infrared_projects at AIT endpoint
ideally this task is only run once as initial setup - and then returns from cache
"""
@app.task()
def setup_infrared_projects_for_cityPyo_user(user_id: str, force_recreation: bool):
    
    if not force_recreation:
        # Check cache. If cached, return result from cache.     
        key = get_cache_key_setup_task(city_pyo_user=user_id)
        group_result_id = cache.retrieve(key=key)

        if not group_result_id == {}:
            print("retrieving infrared projects from cache")
            return group_result_id
        else: 
            print("could not find project setup in cache!!")

    # else: Initial setup of endpoint: create projects at endpoint and export as json
    bboxes = get_grasbrook_bboxes()
    infrared_user = InfraredUser()
    infrared_user_json = infrared_user.export_to_json()
    task_group = group([create_infrared_project.s(infrared_user_json, user_id, list(bbox.exterior.coords), bbox_id) for bbox_id, bbox in enumerate(bboxes)])
    group_result = task_group()
    print("group task for creating projects = ", group_result)
    group_result.save()

    
    return group_result.id

# trigger calculation for a infrared project
@app.task()
def trigger_calculation(wind_scenario, buildings, project):
    return start_calculation_for_project(wind_scenario, buildings, project)


# triggers a computation for each of the infrared_projects and returns them as group result
@app.task()
def compute_task(
    scenario_hash: str,
    buildings_hash: str,
    scenario: dict,
    buildings: dict,
    infrared_projects: list,
    ):
    
    # Check cache. If cached, return result from cache.
    key = get_cache_key_compute_task(scenario_hash=scenario_hash, buildings_hash=buildings_hash)
    result = cache.retrieve(key=key)
    if not result == {}:
        return result

    # trigger calculation and collect result for project in infrared_projects
    task_group = group(
        [
            chain(
                trigger_calculation.s(scenario, buildings, project), # returns result_uuid
                collect_infrared_result.s(project) # collect_result will result_uuid as first argument
                ) 
            for project in infrared_projects
        ]
    )
    
    group_result = task_group()
    group_result.save()
    
    return group_result.id


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get('state')
    args = kwargs.get('args')
    result = kwargs.get('retval')

    # cache result of task "setup_infrared_projects_for_cityPyo_user" where the first argument is the user id (md5 format)
    if len(args) == 2 and is_valid_md5(args[0]):
        # Cache only succeeded tasks
        if state == "SUCCESS":
            key = get_cache_key_setup_task(city_pyo_user=args[0])
            cache.save(key=key, value=result)
            print("cached infrared project setup with key %s" % key)

    # also cache the "compute_task" task where the first 2 arguments are hashes
    elif len(args) > 2 and is_valid_md5(args[0]) and is_valid_md5(args[1]):
        # Cache only succeeded tasks
        if state == "SUCCESS":
            key = get_cache_key_compute_task(scenario_hash=args[0], buildings_hash=args[1])
            cache.save(key=key, value=result)
            print("cached result with key %s" % key)
