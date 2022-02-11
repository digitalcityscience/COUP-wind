# Wind Module
A module that will accept requests to calculate wind-comfort for a CityPyO user. 
Inputs are: 
- Wind speed
- Wind Direction
- CityPyO user id (used to get the building geometries from CityPyO)

Provides results as geojson or png. Results are calculated by the Infrared API of AIT.

Example result:
![image](https://user-images.githubusercontent.com/4631906/153575034-c173cb24-2ac5-444e-9f20-1ec64f1f5394.png)

#### Wind Comfort Result 

The "wind comfort" service predicts a plane of Lawson Criteria categories, given an input wind direction and speed. 
The returned normalised values represent categories as seen in the following table:

| value | lawson criteria category |
| ----- | ------------------------ |
| `0.0` | "Sitting Long"           |
| `0.2` | "Sitting Short"          |
| `0.4` | "Walking Slow"           |
| `0.6` | "Walking Fast"           |
| `0.8` | "Uncomfortable"          |
| `1.0` | "Dangerous"              |

## USAGE
Results are obtained through a 3 step process:
- **Trigger a calculation**: POST Request to /windtask 
    - Params: 
        ```
        - "wind_speed": INT ; [km/h] ;
        - "wind_direction": INT [0-360°] (0 being north, 90 east); 
        - "city_pyo_user": YOUR_CITYPYO_USER_ID  
        ```
    - Returns the task id of the celery task:
        ```json { "taskId": __TASK_ID__ } ```
 - **Get result of the celery task**: GET Request to /tasks/__TASK_ID__
    - Returns a group task id:
        ```json {"result": __GROUP_TASK_ID__ } ```
 - **Get result of the group task**: GET Request to /grouptasks/__GROUP_TASK_ID__
    - Param: 
        ``` "result_format": "geojson" || "png" ``` 
    - Returns the actual result, accompanied by some meta information on group task calculation progress.
      ``` {
            "results": { __RESULT_OBJECT__ },
            "grouptaskProcessed": boolean,
            "tasksCompleted": 1,
            "tasksTotal": 7
            }
        ```
            
        __RESULT_OBJECT__ for result_type "geojson":
        ``` { "results": {"type": "FeatureCollection", "features": [...] }}  ```
        
        __RESULT_OBJECT__ for result_type "png":
        
        ``` "results": {
        "bbox_coordinates": [
            [
                LAT,
                LONG
            ],
            ...,
        ],
        "bbox_sw_corner": [
            [
                LAT,
                LONG
            ]
        ],
        "image_base64_string": "PNG_STRING",
        "img_height": PIXELS_Y,
        "img_width": PIXELS_X
    } 
    ```


# RUN LOCALLY 
- clone repo
- create venv, install requirements

- Export ENV variables (see below)
- RUN _docker-compose up redis_ to start only the redis docker
- Activate venv
- RUN _celery -A tasks worker --loglevel=info --concurrency=8 -n worker4@%h_  
- RUN entrypoint.py
- RUN the mock-api by _docker-compose up ait-mock-api_ 
- Test by running test_polling_wind.py

### ENV Variables
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASS=G0rDkQtRcl!E
      - INFRARED_URL=http://ait-mock-api:5555/
      - INFRARED_USERNAME=test
      - INFRARED_PASSWORD=test
      - CITY_PYO=https://api.hcu-dev.de/citypyo/

## Technical Setup
In general this software is a wrapper around the Infrared AIT api.
The software takes care of 
- subdividing the area of interest into 300m x 300m bboxes (projects) for calculation
- creation/updating of "projects" at Infrared. Each project contains a set of buildings and calculation of wind-comfort is run per project.
- translating geospatial data into the local coordinates and format of AIT projects 
- automated merging of results at bbox/project intersections
- converting of a project's result to geojson
- provision of result geojsons as png if requested
- keeping your projects at AIT api alive (by regular requests to them)


### AIT api & mock api
The AIT api is a GraphQL api which allows creation and updating of projects. Calculation of results per project.
The mock api mocks this behaviour and will always return the same mock result.

# TO BE DESCRIBED

### caching
#


## Celery
This sample project shows how to use Celery to process task batches asynchronously. 
For simplicity, the sum of two integers are computed here. In order to simulate the 
complexity, a random duration (3-10 seconds are put on the processing).
Using Celery, this tech stack offers high scalability. For ease of installation, 
Redis is used here. Through Redis the tasks are distributed to the workers and also 
the results are stored on Redis.

Wrapped with an API (Flask), the stack provides an interface for other services. 
The whole thing is then deployed with Docker.

## Design
The task batches are commissioned via a endpoint (```POST, /grouptasks```) (see Usage). 
The client receives a response with a Group-Task-Id and a list of TaskIds. 
Using polling, the client can query the status of the GroupTask 
(```GET, /grouptasks/<grouptask_id>```) or the status of a Task 
(```GET, /tasks/<task_id>```).

## Caching
After a task has been successfully processed, the result is cached on Redis along with 
the input parameters. The result is then returned when a (different) task has the same 
input parameters and is requested.

## TechStack
- Python
- Celery
- Redis
- Flask
- Docker

## Start
1. ```docker-compose build```
2. ```docker-compose up -d```


## Usage [DEPRECATED]
### Create a GroupTask
Request:
```bash
curl -X POST http://localhost:5000/grouptasks -H 'Content-type: application/json' \
    -d '{"tasks": [{"paramB" : 5, "paramA": 1}, {"paramB" : 10, "paramA": 9}, \
    {"paramB" : 13, "paramA": 12}, {"paramB" : 1, "paramA": 8}]}'
```

Response:
```json
{
    "grouptaskId" : "858c8724-03c4-4027-b1e9-4185545aa54d",
    "taskIds" : [
        "55de4727-c7ad-4c5d-9c72-242a6558d65a",
        "12ae3364-f69b-41b9-ad82-c1b8a3e077b8",
        "4012aa3e-d5a0-4654-8290-00537de97eaf",
        "16fbda42-a4c4-4022-b373-e2fc7f13cbcd"
    ]
}
```

### Get GroupTask-Result
Request:
```
curl -X GET http://localhost:5000/grouptasks/858c8724-03c4-4027-b1e9-4185545aa54d
```

**Hint**: This request can be used for polling. The poll abort condition can be set to "groupTaskProcessed != True". 
While processing the results of processed tasks are published in "results" and can be used to display the progress.


Response:
```json
{
    "grouptaskId" : "858c8724-03c4-4027-b1e9-4185545aa54d",
    "grouptaskProcessed" : false,
    "grouptaskSucceeded" : false,
    "results": [
      6,
      19,
      25
    ],
    "tasksCompleted" : 3,
    "tasksTotal" : 5
}
```
### Get single Task-Result
Request:
```
curl -X GET http://localhost:5000/tasks/55de4727-c7ad-4c5d-9c72-242a6558d65a
```
Response:
```json
{
    "result" : 6,
    "resultReady" : true,
    "taskId" : "55de4727-c7ad-4c5d-9c72-242a6558d65a",
    "taskState" : "SUCCESS",
    "taskSucceeded" : true
}
```

## Commands
### Start worker
```celery -A tasks worker --loglevel=info```

### Monitoring Redis

List Tasks:
- ```redis-cli -h HOST -p PORT -n DATABASE_NUMBER llen QUEUE_NAME```

List Queues:
- ```redis-cli -h HOST -p PORT -n DATABASE_NUMBER keys \*```
