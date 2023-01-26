import os

from flask import Flask, request, abort, make_response, jsonify
from flask_compress import Compress
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from http import HTTPStatus

from celery_app import app as celery_app
from celery.result import AsyncResult, GroupResult

import werkzeug
from werkzeug.security import generate_password_hash, check_password_hash


from services import check_infrared_projects_still_exist, get_calculation_input, get_infrared_projects_from_group_task, convert_result_to_png
from wind.data import summarize_multiple_geojsons_to_one
from wind.wind_scenario_params import ScenarioParams
import tasks


app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
Compress(app)

auth = HTTPBasicAuth()

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_PASSWORD = os.getenv('CLIENT_PASSWORD')

pw_hashes = {
    CLIENT_ID: generate_password_hash(CLIENT_PASSWORD)
}

@auth.verify_password
def verify_password(client_id, password):
    if client_id in pw_hashes and \
            check_password_hash(pw_hashes.get(client_id), password):
        return client_id


@auth.error_handler
def auth_error(status):
    return make_response(
        jsonify({'error': 'Access denied.'}),
        status
    )


@app.errorhandler(werkzeug.exceptions.NotFound)
def not_found(exception: werkzeug.exceptions.NotFound):
    return make_response(
        jsonify({'error': "Could not find the requested url"}),
        404
    )


@app.errorhandler(werkzeug.exceptions.BadRequest)
def bad_request(exception: werkzeug.exceptions.BadRequest):
    message = str(exception)

    print("this is the exception", message)

    return make_response(
        jsonify({'error': message}),
        400
    )


# tries to find the calculation result in cache, otherwise returns None
def find_calc_task_in_cache(request_json):
    try:
        calc_task = tasks.get_result_from_cache.delay(*get_calculation_input(request_json, hashes_only=True))
    except Exception:
        print("Result not yet in cache")
        return None

    print("found group task for calculation in cache. Task ID", calc_task.id)
    # test if result can be restored        
    try:
        async_result = AsyncResult(calc_task.id, app=celery_app)
        group_result = GroupResult.restore(async_result.get(), app=celery_app)
        result_array = [result.get() for result in group_result.results if result.ready()]
    except Exception as e:
        print("But obtaining results from cache caused error.", e)
        return None

    # return calc task
    return calc_task


# tries to find infrafred project setup in cache and, otherwise returns None
def find_infrared_projects_in_cache(cityPyo_user):
    try:
        group_task_projects_creation = tasks.get_project_setup_from_cache.delay(cityPyo_user)
    except:
        print("Infrafred Project setup for cityPyo User not in cache")
        return None

    try:
        infrared_projects = get_infrared_projects_from_group_task(group_task_projects_creation)
    except:
        print("Obtaining results from cache caused error.")
        return None

    print("Infrared projects found in cache", [ip["project_uuid"] for ip in infrared_projects])
    return infrared_projects


@app.route("/check_projects_for_user", methods=["POST"])
def check_projects_for_user():
    if not request.json:
        print("no request json.")
        abort(400, "No request.json")

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


@app.post("/trigger_calculation")
@auth.login_required
def trigger_calculation():
    # Validate request
    if not request.json:
        abort(400)
    try:
        # are all relevant params delivered?
        __wind_scenario = ScenarioParams(request.json, "wind")  # todo get wind from endpiont
        city_pyo_user_id = request.json["city_pyo_user"]
    except KeyError as missing_arg:
        abort(400, "Bad Request. Missing argument: %s" % missing_arg)
    except Exception as e:
        abort(400, "Bad Request. Exception: %s" % e)

    # wind_scenario["result_type"] = "wind"  # TODO make route for sun, ...

    calc_task = find_calc_task_in_cache(request.json)
    if not calc_task:
        try:
            # check if projects are cached and still exist. Otherwise recreate them at endpoint.
            infrared_projects = find_infrared_projects_in_cache(city_pyo_user_id)
            if not check_infrared_projects_still_exist(infrared_projects):
                """
                Trigger the recreation of projects at Infrared endpoint,
                which takes several minutes.
                Ask the user to try again in 5 min.
                """
                setup_task = tasks.setup_infrared_projects_for_cityPyo_user.delay(city_pyo_user_id)

                abort(HTTPStatus.GATEWAY_TIMEOUT, (
                    f"Setup in process. This may take several minutes. \n"
                    f"Check with GET .../check_on_singletask/{ setup_task.id } if setup is ready. \n"
                    f"Then repost your calculation request."
                    )    
                )

            # compute result
            print("Sending calculation request to AIT Infrared.")
            calc_task = tasks.compute_task.delay(*get_calculation_input(request.json), infrared_projects)

        except Exception as e:
            abort(500, e)

    group_task_id = calc_task.get()  # use group task id to get results of the calc_task.
    response = {'groupTaskId': group_task_id}
    
    return make_response(
        jsonify(response),
        HTTPStatus.OK,
    )


# route to collect results
@app.route("/collect_results/<grouptask_id>", methods=['GET'])
@auth.login_required
def get_grouptask(grouptask_id: str):
    """
    Route to get results of group tasks.
    Group tasks contain several sub-tasks.
    Returns a result containing the result of all sub-tasks that are ready
    """
    request_args = request.args.to_dict()
    result_format = request_args.get("result_format")
    print(f"Requested result of group task id {grouptask_id} , result_format {result_format}")

    group_result = GroupResult.restore(grouptask_id, app=celery_app)
    total_results_count = len(group_result.results)
    results = [result.get() for result in group_result.results if result.ready()]
    ready_results_count = len(results)
    print(f"{len(results)} of { len(group_result.results) } tasks ready.")

    
    if results:
        # first summarize the results into 1 geojson
        results = summarize_multiple_geojsons_to_one([result["geojson"] for result in results])
    
        if result_format == "png":
            print("converting result to png")
            results = convert_result_to_png(results)

    else:
        if result_format == "geojson":
            # return empty geojson if no results
            results = {
                "type": "FeatureCollection",
                "features": []
            }

    # Fields available
    # https://docs.celeryproject.org/en/stable/reference/celery.result.html#celery.result.ResultSet
    response = {
        'grouptaskId': group_result.id,
        'tasksCompleted': group_result.completed_count(),
        'tasksTotal': total_results_count,
        'grouptaskProcessed': total_results_count == ready_results_count,
        'results': results
    }

    return make_response(
        response,
        HTTPStatus.OK,
    )



@app.route("/check_on_singletask/<task_id>", methods=['GET'])
@auth.login_required
def get_task(task_id: str):
    """
    This route is for debugging only.

    Route to check status of single tasks.
    Single tasks can be setup tasks or calculation tasks
    Calculation tasks actually return a group task ID as "result".
    This group task then contains the actual calculation results. 
    """
    async_result = AsyncResult(task_id, app=celery_app) # restore task

    # Fields available
    # https://docs.celeryproject.org/en/stable/reference/celery.result.html#celery.result.Result
    response = {
        'taskId': async_result.id,
        'taskState': async_result.state,
        'taskSucceeded': async_result.successful(),
        'resultReady': async_result.ready(),
    }
    if async_result.ready():
        response['result'] = async_result.get()

    return make_response(
        response,
        HTTPStatus.OK,
    )


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)
