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


# tries to find the calculation result in cache, otherwise returns None
def find_result_in_cache(request_json):
    try:
        result = tasks.get_result_from_cache.delay(*get_calculation_input(request_json, hashes_only=True))
        result.get()  # test if result can be restored        
        print("found result in cache!")
        return result
    
    except Exception:
        print("Result not yet in cache")
        return None


# tries to find infrafred project setup in cache and, otherwise returns None
def find_infrared_projects_in_cache(cityPyo_user):
    try:
        group_task_projects_creation = tasks.get_project_setup_from_cache.delay(cityPyo_user)
        infrared_projects = get_infrared_projects_from_group_task(group_task_projects_creation)

        print("Infrared projects found in cage", [ip["project_uuid"] for ip in infrared_projects])
        return infrared_projects
    
    except Exception as e:
        print(e)
        print("Infrafred Project setup for cityPyo User not in cache")
        return None
    

@app.route("/check_projects_for_user", methods=["POST"])
def check_projects_for_user():
    if not request.json:
        print("no request json.")
        abort(400)
    
    check_successful = False
    cityPyo_user = request.json["city_pyo_user"]
    print("checking project status at AIT for user ", cityPyo_user)
    
    try: 
        # retrieve infrared projects from cache
        infrared_projects = find_infrared_projects_in_cache(cityPyo_user)
        if check_infrared_projects_still_exist(infrared_projects):
            # projects still exist, nothing to do.
            return "success"
        else:
            print("projects missing for cityPyo user", cityPyo_user)
    
    except Exception as e:
        print("Exception occured when checking for projects. ", e)
        print("Trying to reset now")    
    
    # try to recreate the projects and check again if projects at endpoint and local are the same.
    try:
        recreation_group_task = tasks.setup_infrared_projects_for_cityPyo_user.delay(user_id=cityPyo_user)
        infrared_projects = get_infrared_projects_from_group_task(recreation_group_task)
        check_successful = check_infrared_projects_still_exist(infrared_projects)
    except Exception as e:
            print("Failed for cityPyo user ", cityPyo_user)
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
    result = find_result_in_cache(request.json)
    if not result:
        try:
            # check if projects are cached and still exist. Otherwise recreate them at endpoint.
            infrared_projects = find_infrared_projects_in_cache(city_pyo_user_id)        
            if not check_infrared_projects_still_exist(infrared_projects):
                group_task_id_projects_creation = tasks.setup_infrared_projects_for_cityPyo_user.delay(city_pyo_user_id)
                infrared_projects = get_infrared_projects_from_group_task(group_task_id_projects_creation)

            # compute result
            result = tasks.compute_task.delay(*get_calculation_input(request.json), infrared_projects)
        
        except Exception as e:
            abort(500, e)
    
    response = {'taskId': result.id}
    print("response returned ", response)

    # return jsonify(response), HTTPStatus.OK
    return make_response(
        jsonify(response),
        HTTPStatus.OK,
    ) 



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
