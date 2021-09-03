from celery import group
from celery.result import GroupResult

from tasks import compute_ait_uuid


def compute(complex_tasks: list) -> GroupResult:
    # Validate input
    # for complexTask in complex_tasks:
    #     if type(complexTask) != ComplexTask:
    #         raise ValueError('Expected type ComplexTask but got %s' % type(complexTask))

    # Logic: geographische project area wird in 8 sub-areas unterteilt

    task_group = group([compute_ait_uuid.s(ct) for ct in complex_tasks])
    group_result = task_group()
    group_result.save()

    return group_result
