from http import HTTPStatus
from wind.data import summarize_multiple_geojsons_to_one
from services import check_infrared_projects_still_exist, get_calculation_input, get_infrared_projects_from_group_task
from wind.wind_scenario_params import ScenarioParams

from celery.result import AsyncResult, GroupResult
from flask import Flask, request, abort, make_response, jsonify

import tasks
from mycelery import app as celery_app
import werkzeug
from flask_cors import CORS, cross_origin
from flask_compress import Compress


app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
Compress(app)


@app.errorhandler(werkzeug.exceptions.NotFound)
def not_found(exception: werkzeug.exceptions.NotFound):

    return make_response(
        jsonify({'error': "Could not find the requested url"}),
        404
    )


@app.errorhandler( werkzeug.exceptions.BadRequest)
def bad_request(exception:  werkzeug.exceptions.BadRequest):
    message = str(exception)

    print("this is the exception", message)
    
    return make_response(
        jsonify({'error': message}),
        400
    )


@app.route("/check_projects_for_user", methods=["POST"])
def check_projects_for_user():
    if not request.json:
        print("no request json.")
        abort(400)
    
    cityPyo_user = request.json["city_pyo_user"]
    check_successful = False
    
    try: 
        group_task = tasks.setup_infrared_projects_for_cityPyo_user.delay(cityPyo_user, False)
        infrared_projects = get_infrared_projects_from_group_task(group_task)
        print(infrared_projects)
        if check_infrared_projects_still_exist(infrared_projects):
            # projects still exist, nothing to do.
            return "success"
    except Exception as e:
        print("exception in first check ", e)
    
    if not check_successful:
        print("Projects missing. Need to recreate projects now.")
        # Try recreating the projects. 
        # Will get the new login credentials for our Infrared_User and save it to projects
        try:
            recreation_group_task = tasks.setup_infrared_projects_for_cityPyo_user.delay(user_id=cityPyo_user, force_recreation=True)
            infrared_projects = get_infrared_projects_from_group_task(recreation_group_task)
            check_successful = check_infrared_projects_still_exist(infrared_projects)

        except Exception as e:
            print("cannot check if projects exist. There might be a general error: ", e)
            abort(500)

    if not check_successful:
        print("check for projects failed failed")
        print("these projects should exist")
        print(get_infrared_projects_from_group_task(recreation_group_task))
        abort(500)
        
    if check_successful:
        return "success"
        

@app.route("/windtask", methods=["POST"])
def process_task():
    # Validate request
    if not request.json:
        abort(400)
    try:
        # are all relevant params delivered?
        wind_scenario = ScenarioParams(request.json, "wind")  # todo get wind from endpiont
        city_pyo_user_id = request.json["city_pyo_user"]
    except KeyError as missing_arg:
        abort(400, "Bad Request. Missing argument: %s" % missing_arg)
    except Exception as e:
        abort(400, "Bad Request. Exception: %s" %e)

    #wind_scenario["result_type"] = "wind"  # TODO make route for sun, ...

    # Parse requests
    try:
        infrared_projects_group_task = tasks.setup_infrared_projects_for_cityPyo_user.delay(city_pyo_user_id, False)
        infrared_projects = get_infrared_projects_from_group_task(infrared_projects_group_task)

        if not check_infrared_projects_still_exist(infrared_projects):
            print("Infrared Projects do no longer exist at endpopint")
            # if projects were deleted at endpoint, enforce recreation and wait for task to be finished.
            infrared_projects_group_task =tasks.setup_infrared_projects_for_cityPyo_user.delay(city_pyo_user_id, True)
            infrared_projects = get_infrared_projects_from_group_task(infrared_projects_group_task)

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


@app.route("/grouptasks/<grouptask_id>", methods=['GET'])
def get_grouptask(grouptask_id: str):
    group_result = GroupResult.restore(grouptask_id, app=celery_app)
    result_array = [result.get() for result in group_result.results if result.ready()]

    if result_array:
        results = summarize_multiple_geojsons_to_one([result["geojson"] for result in result_array])
    else:
        # return empty geojson if no results
        results ={
            "type": "FeatureCollection",
            "features": []
        }
    
    # TODO format result here. geojson to png?

    # Fields available
    # https://docs.celeryproject.org/en/stable/reference/celery.result.html#celery.result.ResultSet
    response = {
        'grouptaskId': group_result.id,
        'tasksCompleted': group_result.completed_count(),
        'tasksTotal': len(group_result.results),
        'grouptaskProcessed': group_result.ready(),
        'grouptaskSucceeded': group_result.successful(),
        'results': results
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
