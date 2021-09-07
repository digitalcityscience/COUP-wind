from requests.api import request
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
def collect_infrared_result(uuid: str, result_format) -> dict:
    # collect the result from AIT endpoint and format it
    return collect_and_format_result_from_ait(uuid, result_format)


@app.task()
def compute_wind_request(request_json: dict):
    wind_scenario = WindScenarioParams(request_json)
    
    # Check cache. If cached, return result from cache.
    key = wind_scenario.hash
    result = cache.retrieve(key=key)
    if not result == {}:
        return result
    
    # Trigger calculation at AIT Infrared endpoint
    infrared_projects = start_calculation(wind_scenario, "wind")
    
    # collect result for each of the infrared projects
    result_format = wind_scenario.result_format
    task_group = group([collect_infrared_result.s(project, result_format) for project in infrared_projects])
    group_result = task_group()
    group_result.save()
    
    return group_result.id


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get('state')
    args = kwargs.get('args')
    result = kwargs.get('retval')

    if state == "SUCCESS":
        try:
            # if you can create WindScenarioParams from the request - then cache the result
            params = WindScenarioParams(args[0])
            cache.save(key=params.hash, value=result)
        
        except:
            # do not cache
            pass