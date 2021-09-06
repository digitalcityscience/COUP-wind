import time
from pprint import pprint

import requests

headers = {
    'Content-type': 'application/json',
}

data = '{ "city_pyo_user": "", "wind_speed": 25, "wind_direction": 270, "result_format": "geojson", "custom_roi": [], "hash": "werwererererwer" }'

response = requests.post('http://localhost:5000/windtask', headers=headers, data=data)

task_id = response.json()['taskId']
print("Received taskId:", task_id)

task_succeeded = False
grouptask_id = None
print("Listen for task-result. Result is the id of the GroupTask.")
while not task_succeeded:
    response = requests.get('http://localhost:5000/tasks/{}'.format(task_id))
    print(response)
    task_succeeded = response.json()['taskSucceeded']
    time.sleep(1)


grouptask_id = response.json()['result']
print("Got id from GroupTasks (%s). Now start polling for Zwischenergebnisse" % grouptask_id)

results_completed = False
while not results_completed:
    response = requests.get('http://localhost:5000/grouptasks/{}'.format(grouptask_id)).json()
    results_completed = response['grouptaskProcessed']
    pprint(response)
    time.sleep(1)

print("Fertig!")
