from wind.wind_scenario_params import WindScenarioParams
from wind.main import collect_and_format_result_from_ait, start_calculation
from celery import signals, group
from celery.utils.log import get_task_logger

from cache import Cache
from mycelery import app

from wind.main import start_calculation

logger = get_task_logger(__name__)
cache = Cache()


@app.task()
def collect_result(uuid: str, result_format) -> dict:
    # Start computing
    result = collect_and_format_result_from_ait(
        uuid,
        result_format
    )

    return {"subtask_result": result}


@app.task()
def compute_ait_uuid(project: str) -> dict:
    # Start computing
    import time, random
    time.sleep(random.randint(5, 10))

    import uuid
    uuid = uuid.uuid4()

    print("Subtask %s processed" % uuid)
    return {"subtask_result": "Ergebnis von %s" % uuid}


# class ComputeWindRequestParams:
#     def __init__(self, wind_speed: int, wind_direction: int, hash: str):
#

@app.task()
def compute_wind_request(request_json: dict):
    wind_scenario = WindScenarioParams(request_json)
    
    # Check cache. If cached, return result from cache.
    key = wind_scenario.hash
    result = cache.retrieve(key=key)
    if not result == {}:
        return result
    
    import uuid
    import time



    print("Computation incoming for wind_speed: %s, wind_direction: %s, and city_pyo_user : %s" % (
        wind_scenario.wind_speed, 
        wind_scenario.wind_direction,
        wind_scenario.city_pyo_user
    ))

    print("Trigger calculation at AIT endpoint")
    uuids = start_calculation(wind_scenario)
    print("uuids from AIT ", uuids)


    print("Start processing subtasks given by AIT")
    task_group = group([compute_ait_uuid.s(uuid) for uuid in uuids])
    #task_group = group([collect_result.s(uuid, wind_scenario.result_format) for uuid in uuids])
    group_result = task_group()
    group_result.save()
    
    return group_result.id


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get('state')
    args = kwargs.get('args')
    result = kwargs.get('retval')

    # Cache only succeeded tasks
    if state == "SUCCESS" and type(args[0]) == WindScenarioParams:
        key = args[0].hash  # Params of compute_ait_uuid() function
        cache.save(key=key, value=result)
