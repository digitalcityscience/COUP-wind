from http import HTTPStatus
from services import get_calculation_input
from wind.wind_scenario_params import WindScenarioParams

from celery.result import AsyncResult, GroupResult
from flask import Flask, request, abort, make_response, jsonify

import tasks
from mycelery import app as celery_app
import werkzeug
import time


app = Flask(__name__)


@app.errorhandler(werkzeug.exceptions.NotFound)
def not_found(exception: werkzeug.exceptions.NotFound):

    return make_response(
        jsonify({'error': "Could not find the requested url"}),
        404
    )


@app.errorhandler( werkzeug.exceptions.BadRequest)
def bad_request(exception:  werkzeug.exceptions.BadRequest):
    message = str(exception)
    
    return make_response(
        jsonify({'error': message}),
        400
    )



@app.route("/task", methods=["POST"])
def process_task():
    # Validate request
    if not request.json:
        abort(400)
    try:
        # are all relevant params delivered?
        wind_scenario = WindScenarioParams(request.json)
        city_pyo_user_id = request.json["city_pyo_user"]
    except KeyError as missing_arg:
        abort(400, "Bad Request. Missing argument: %s" % missing_arg)
    except Exception as e:
        abort(400, "Bad Request. Exception: %s" %e)

    #wind_scenario["result_type"] = "wind"  # TODO make route for sun, ...

    # Parse requests
    try:
        # todo how to trigger tasks again??
        infrared_projects_group_task = tasks.create_infrared_projects_for_cityPyo_user.delay(city_pyo_user_id)
        print("group task id", infrared_projects_group_task)
        result = infrared_projects_group_task.get()
        print("result of infrared project task", result, type(result))
        
        print("infrared_projects_group_task_id")
        print(infrared_projects_group_task.id)
        print(type(infrared_projects_group_task.id))
        group_result = GroupResult.restore(result, app=celery_app)
        print(group_result, type(group_result))
        while not group_result.ready():
            print("waiting for infrared projects to be setup")
            time.sleep(2)
        
        infrared_projects = [result.get() for result in group_result.results if result.ready()]
        print("everything setup :)")
        print(infrared_projects)

        # TODO  test if projects and infrared user really still exist and force recreation if not.
        single_result = tasks.compute_task.delay(*get_calculation_input(request.json), infrared_projects)
        response = {'taskId': single_result.id}
        print("response returned ", response)

        # return jsonify(response), HTTPStatus.OK
        return make_response(
            jsonify(response),
            HTTPStatus.OK,
        )
    except KeyError:
        return bad_request("Payload not correctly structured.")




@app.route("/windtask", methods=['POST'])
def process_windtask():
    # Validate request
    if not request.json:
        abort(400)
    try:
        # are all relevant params delivered?
        WindScenarioParams(request.json)
    except KeyError as missing_arg:
        abort(400, "Bad Request. Missing argument: %s" % missing_arg)
    except Exception as e:
        abort(400, "Bad Request. Exception: %s" %e)


    # Parse requests
    try:
        single_result = tasks.compute_task.delay(request.json)
        response = {'taskId': single_result.id}

        # return jsonify(response), HTTPStatus.OK
        return make_response(
            jsonify(response),
            HTTPStatus.OK,
        )
    except KeyError:
        return bad_request("Payload not correctly structured.")


@app.route("/grouptasks/<grouptask_id>", methods=['GET'])
def get_grouptask(grouptask_id: str):
    group_result = GroupResult.restore(grouptask_id, app=celery_app)
    result_array = [result.get() for result in group_result.results if result.ready()]



    # TODO format result here. also union geojsons , then geojson to png.


    # TODO - we need to cache the input variables of the grouptask. check for desired output format. might be png.
    # combine results to 1 geojson
    geojson = {
        "type": "FeatureCollection",
        "name": "wind_result_" + grouptask_id,
        "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:EPSG::4326" } },
        "features": [feat for result in result_array for feat in result]
    }

    # Fields available
    # https://docs.celeryproject.org/en/stable/reference/celery.result.html#celery.result.ResultSet
    response = {
        'grouptaskId': group_result.id,
        'tasksCompleted': group_result.completed_count(),
        'tasksTotal': len(group_result.results),
        'grouptaskProcessed': group_result.ready(),
        'grouptaskSucceeded': group_result.successful(),
        'results': geojson
    }

    return make_response(
        response,
        HTTPStatus.OK,
    )


@app.route("/tasks/<task_id>", methods=['GET'])
def get_task(task_id: str):
    print("looking for results of this id", task_id)
    async_result = AsyncResult(task_id, app=celery_app)
    print(async_result)

    # Fields available
    # https://docs.celeryproject.org/en/stable/reference/celery.result.html#celery.result.Result
    response = {
        'taskId': async_result.id,
        'taskState': async_result.state,
        'taskSucceeded': async_result.successful(),
        'resultReady': async_result.ready(),
    }
    if async_result.ready():
        print(type(async_result.get()))
        response['result'] = async_result.get()

    return make_response(
        response,
        HTTPStatus.OK,
    )



if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5003)
