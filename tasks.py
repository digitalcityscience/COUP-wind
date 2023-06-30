from celery import signals, group, chain
from celery.utils.log import get_task_logger
from celery_app import app
from cache import Cache

from services import get_cache_key_compute_task, get_cache_key_setup_task, hash_dict

from wind.infrared_user import InfraredUser
from wind.main import \
    get_bboxes, \
    create_infrared_project_for_bbox_and_user, \
    start_calculation_for_project, \
    collect_result_for_project


logger = get_task_logger(__name__)
cache = Cache()


@app.task()
def get_result_from_cache(
    sim_type: str,
    buildings_hash: str,
    calc_input_hash: str
):
    # Check cache. If cached, return result from cache.
    key = get_cache_key_compute_task(sim_type, buildings_hash, calc_input_hash)
    result = cache.retrieve(key=key)
    if not result == {}:
        return result
    else: 
        raise Exception("Could not find result in cache")


@app.task()
def get_project_setup_from_cache(user_id):
    # Check cache. If cached, return result from cache.     
    key = get_cache_key_setup_task(city_pyo_user=user_id)
    print(key)
    group_result_id = cache.retrieve(key=key)
    
    if not group_result_id == {}:
        print("retrieving infrared projects from cache")
        return group_result_id
    else: 
        print("could not find project setup in cache!!")
        raise Exception("Could not find setup in cache")



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
def setup_infrared_projects_for_cityPyo_user(user_id: str) -> str:
    
    # Initial setup of endpoint: create projects at endpoint and export as json
    bboxes = get_bboxes(user_id)
    infrared_user = InfraredUser()
    infrared_user_json = infrared_user.export_to_json()
    task_group = group([create_infrared_project.s(infrared_user_json, user_id, list(bbox.exterior.coords), bbox_id) for bbox_id, bbox in enumerate(bboxes)])
    group_result = task_group()
    print("group task for creating projects = ", group_result)
    group_result.save()

    return group_result.id

# triggers a computation for each of the infrared_projects and returns them as group result
@app.task()
def compute_task(
    sim_type: str,
    infrared_projects: list,
    calc_settings: dict,
    buildings_hash: str # just for caching
    ):
    # trigger calculation and collect result for project in infrared_projects
    task_group = group(
        [
            # create task chain for each project. tasks in chain will be executed sequentially
            chain(
                trigger_calculation.s(sim_type, calc_settings, project), # returns result_uuid
                collect_infrared_result.s(project) # collect_result will have result_uuid as first argument
                )
            for project in sorted(infrared_projects, key=lambda d: d['building_count'], reverse=True) # sort projects by building count (relevant results first)
        ]
    )
    
    group_result = task_group()
    group_result.save()

    return group_result.id

# trigger calculation for a infrared project
@app.task()
def trigger_calculation(sim_type, calc_settings, project):
    return start_calculation_for_project(sim_type, calc_settings, project)


@signals.task_postrun.connect()
def task_postrun_handler(task_id, task, sender=None, *args, **kwargs):
    state = kwargs.get('state')
    func_args = kwargs.get('args')
    func_kwargs = kwargs.get('kwargs') 
    result = kwargs.get('retval')

    """ Debugging info
    print(
        f'task with name {task} executed. \
        \n sender {sender} \
        \n state {state} \
        \n args {func_args} \
        \n kwargs {func_kwargs} \
        \n result {result}'
    )
    """

    # cache result of task "setup_infrared_projects_for_cityPyo_user"
    if "setup_infrared_projects_for_cityPyo_user" in task.name:
        # Cache only succeeded tasks
        if state == "SUCCESS":
            try:
               city_pyo_user_id = func_args[0]
            except:
                # userid gets provided as kwarg, when function is called by another task.
                city_pyo_user_id = func_kwargs["user_id"]

            key = get_cache_key_setup_task(city_pyo_user=city_pyo_user_id)
            cache.save(key=key, value=result)
            print("cached infrared project setup with key %s" % key)

    # also cache the "compute_task" task where the first 2 arguments are hashes
    elif "compute_task" in task.name:
        # Cache only succeeded tasks
        if state == "SUCCESS":
            try:
                sim_type = func_kwargs["sim_type"]
                buildings_hash = func_kwargs["buildings_hash"]
                calc_settings = func_kwargs["calc_settings"]
            except:
                print("failed recover arguments from compute_task when caching. not caching result.")
                return

            key = get_cache_key_compute_task(sim_type, buildings_hash, hash_dict(calc_settings))
            cache.save(key=key, value=result)
            print("cached result with key %s" % key)
