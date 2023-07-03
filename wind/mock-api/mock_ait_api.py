import json
import uuid
import time

from flask import Flask, request, abort, render_template
from flask_cors import CORS


app = Flask(__name__, template_folder='./')
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


clients = {}



def parseReq(request):
    if request.method == 'POST':
        params = dict(request.json)
    elif request.method == "GET":
        params = {}
        for key in request.args.keys():
            # we have to parse this element by element, to detect duplicate keys
            if len(request.args.getlist(key)) > 1:
                params[key] = request.args.getlist(key)  # duplicate key, store all values as list
            else:
                params[key] = request.args[key]  # default behaviour: store single value
    else:
        abort(400)

    if params and len(params.items()) > 0:
        return params
    else:
        return {}


def get_random_uuid_id():
    return str(uuid.uuid4())


def new_project_response(project_uuid):
    return {
        "data": {
            "createNewProject": {
                "uuid": project_uuid,
                "success": True
            }
        }
    }


def get_client_uuid_for_project_uuid(project_uuid):
    for client in clients.keys():
        if project_uuid in clients[client]["projects"].keys():
            return client


def get_client_uuid_and_project_uuid_for_snapshot(snapshot_uuid):
    print("these are the stored clients", clients)
    for client in clients.keys():
        for project in clients[client]["projects"].keys():
            if snapshot_uuid in clients[client]["projects"][project]["snapshots"].keys():
                return client, project


def new_analysis_output_response(client_uuid, project_uuid, snapshot_uuid, result_uuid):
    with open('wind/mock-api/mock_api_output.json') as fp:
        mock_api_output = json.load(fp)

    return {"data": {
        "getAnalysisOutput": {
            "infraredSchema": {
                "clients": {
                    client_uuid: {
                        "projects": {
                            project_uuid: {
                                "snapshots": {
                                    snapshot_uuid: {
                                        "analysisOutputs": {
                                            result_uuid: mock_api_output
    }}}}}}}}}}}


def snapshot_response(client_uuid, project_uuid, snapshot_uuid):
    return {"data": {
        "getSnapshotsByProjectUuid": {
            "infraredSchema": {
                "clients": {
                    client_uuid: {
                        "projects": {
                            project_uuid: {
                                "snapshots": {snapshot_uuid: {}}
    }}}}}}}}


def project_uuids_response(client_uuid):

    try:
        projects = clients[client_uuid]["projects"]
        print("projects in db", projects)
    except KeyError:
        projects = {}


    return { "data": {
        "getProjectsByUserUuid": {
            "infraredSchema": {
                "clients": {
                    client_uuid: {
                        "projects": projects
    }}}}}}


def get_snapshotUuid_from_query(query):
    import re
    result = re.search('snapshotUuid: (.*)', query)
    return str(result.group(1)).replace('"', '')


def get_Useruuid_from_query(query):
    import re
    result = re.search('userUuid: (.*)', query)
    return str(result.group(1)).replace('"', '')
    
def get_project_name_from_query(query):
    import re
    result = re.search('name: (.*)', query)
    return str(result.group(1)).replace('"', '')


def get_uuid_from_query(query):
    import re
    result = re.search('uuid: (.*)', query)
    return str(result.group(1)).replace('"', '')


@app.route('/api', methods=['POST'])
def query():
    params = parseReq(request)
    
    print("request params in mock api")
    print(params)
    
    query = params["query"]

    if "mutation" in query:
        if "createNewProject" in query:

            print(query)
            time.sleep(30)

            # get client and create project for client
            client_uuid = get_Useruuid_from_query(query)
            project_uuid_id = get_random_uuid_id()
            project_name = get_project_name_from_query(query)
            clients[client_uuid]["projects"][project_uuid_id] = {"projectName": project_name}

            return new_project_response(project_uuid_id)
        
        if "deleteProject" in query:

            print(query)

            # get client and create project for client
            client_uuid = get_Useruuid_from_query(query)
            project_uuid_id = get_uuid_from_query(query)
            del clients[client_uuid]["projects"][project_uuid_id]

            return {'data': {
                'deleteProject': {
                    'success': True
                    }
                }
            }

        if "createNewBuilding" in query:
            return {
                "data": {
                    "createNewBuilding": {
                        "uuid": get_random_uuid_id()
                    }
                }
            }

        if "runServiceWindComfort" in query:
            return {
                "data": {
                    "runServiceWindComfort": {
                        "uuid": get_random_uuid_id()
                    }
                }
            }
        
        if "runServiceSolarRadiation" in query:
            return {
                "data": {
                    "runServiceSolarRadiation": {
                        "uuid": get_random_uuid_id()
                    }
                }
            }
        
        if "runServiceSunlightHours" in query:
                    return {
                        "data": {
                            "runServiceSunlightHours": {
                                "uuid": get_random_uuid_id()
                            }
                        }
                    }

        if "modifyProject" in query:
            return {
                "data":{"modifyProject":{"success":True}}
            }


    if "query" in query:

        if "getProjectsByUserUuid" in query:
            return project_uuids_response(get_uuid_from_query(query))

        if "getSnapshotsByProjectUuid" in query:
            project_uuid = get_uuid_from_query(query)
            client_uuid = get_client_uuid_for_project_uuid(project_uuid)
            snapshot_uuid = get_random_uuid_id()

            clients[client_uuid]["projects"][project_uuid]["snapshots"] = {}
            clients[client_uuid]["projects"][project_uuid]["snapshots"][snapshot_uuid] = {}

            return snapshot_response(client_uuid, project_uuid, snapshot_uuid)


        if "getSnapshotGeometryObjects" in query:
            return {}

        if "getAnalysisOutput" in query:
            # send back empty result sometimes - to mock API calculation time
            import random
            if random.randint(0, 9) > 2:
                return {
                    "data": {
                        "getAnalysisOutput": {
                            "infraredSchema": None
                        }
                    }
                }

            # create fake result
            result_uuid = get_uuid_from_query(query)
            snapshot_uuid = get_snapshotUuid_from_query(query)
            client_uuid, project_uuid = get_client_uuid_and_project_uuid_for_snapshot(snapshot_uuid)

            return new_analysis_output_response(client_uuid, project_uuid, snapshot_uuid, result_uuid)

    
    raise NotImplementedError(query)

@app.route('/', methods=['POST'])
def login():
    params = parseReq(request)
    if not params:
        abort(400)
    username = params.get('username')
    password = params.get('password')
    log_this_request = params.get('log_this_request')


    print("hello", username)
    print(request)

    if username == "":
        abort(400)

    client_uuid = '89012835-d8fc-499c-a183-ac904cb6d766'
    try:
       projects =  clients[client_uuid]["projects"]
    except KeyError:
       clients[client_uuid] = {"projects": {}}

    resp = app.make_response(render_template("mock_response_infrared.html"))
    resp.set_cookie('InFraReD', 'eyJ0eXAi')
    resp.set_cookie('InFraReDClientUuid', client_uuid)


    return resp


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5555)





