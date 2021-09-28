from http import HTTPStatus
from wind.wind_scenario_params import WindScenarioParams

from celery.result import AsyncResult, GroupResult
from flask import Flask, request, abort, make_response, jsonify

import tasks
from mycelery import app as celery_app
import werkzeug


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
        single_result = tasks.compute_wind_request.delay(request.json)
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
    async_result = AsyncResult(task_id, app=celery_app)

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
