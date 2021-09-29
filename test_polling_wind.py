import time
from pprint import pprint

import requests

headers = {
    'Content-type': 'application/json',
}

data = '{ "city_pyo_user": "90af2ace6cb38ae1588547c6c20dcb36", "wind_speed": 26, "wind_direction": 26, "custom_roi": [] }'

#response = requests.post('http://localhost:5000/windtask', headers=headers, data=data)
response = requests.post('http://localhost:5003/task', headers=headers, data=data)

task_id = response.json()['taskId']
print("Received taskId:", task_id)

task_succeeded = False
grouptask_id = None
print("Listen for task-result. Result is the id of the GroupTask.")
while not task_succeeded:
    response = requests.get('http://localhost:5003/tasks/{}'.format(task_id))
    print(response)
    task_succeeded = response.json()['taskSucceeded']
    time.sleep(1)


grouptask_id = response.json()['result']
print("Got id from GroupTasks (%s). Now start polling for Zwischenergebnisse" % grouptask_id)

results_completed = False
while not results_completed:
    response = requests.get('http://localhost:5003/grouptasks/{}'.format(grouptask_id)).json()
    results_completed = response['grouptaskProcessed']
    pprint("tasks completed: %s" % response["tasksCompleted"])
    #pprint("result preview %s" % response["results"][0][0])
    time.sleep(1)

print("Fertig!")
