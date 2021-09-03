from celery import signals, group
from celery.utils.log import get_task_logger

from cache import Cache
from mycelery import app

logger = get_task_logger(__name__)
cache = Cache()


@app.task()
def compute_ait_uuid(uuid: str) -> dict:
    # Check cache. If cached, return result from cache.

    # key = complex_task['hash']
    # result = cache.retrieve(key=key)
    # if not result == {}:
    #     return result

    # Start computing
    # duration = randint(3, 10)
    # logger.info('Compute {0}'.format(key))
    # time.sleep(duration)
    result = uuid
    import time, random
    time.sleep(random.randint(5, 10))
    print("Subtask %s processed" % uuid)
    return {"subtask_result": "Ergebnis von %s" % uuid}


@app.task()
def compute_wind_request(wind_speed: int, wind_direction: int):
    import uuid
    import time

    print("Computation incoming for wind_speed: %s, wind_direction: %s" % (wind_speed, wind_direction))
    print("Start creating subtasks using AIT")
    time.sleep(10)
    uuids = [str(uuid.uuid4()) for i in range(8)]
    print("Start processing subtasks given by AIT")
    task_group = group([compute_ait_uuid.s(uuid) for uuid in uuids])
    group_result = task_group()
    group_result.save()
    # print("Vinh guck mal hier:", type(group_result))
    return group_result.id


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get('state')
    args = kwargs.get('args')
    result = kwargs.get('retval')

    # Cache only succeeded tasks
    # if state == "SUCCESS":
    #     key = args[0]['hash']
    #     cache.save(key=key, value=result)
