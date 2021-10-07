import requests
import os

import wind.queries
from wind.queries import make_query

cwd = os.getcwd()
config = None


class InfraredUser:
    """Class to handle Infrared communication for the InfraredUser"""

    def __init__(self, reset_user_at_endpoint=False, uuid=None, token=None):
        self.uuid = uuid
        self.token = token

        if not self.uuid:
            self.infrared_user_login()

        if reset_user_at_endpoint:
            self.delete_all_projects()

        self.all_projects = self.get_all_projects()

    # logs in infrared user
    def infrared_user_login(self):
        user_creds = {"username": os.getenv("INFRARED_USERNAME"), "password": os.getenv("INFRARED_PASSWORD")}
        request = requests.post(os.getenv("INFRARED_URL"), json=user_creds, headers={'origin': os.getenv('INFRARED_URL')})

        if request.status_code == 200:
            # get the auth token from the returned cookie
            print(request.cookies)
            self.uuid = request.cookies.get("InFraReDClientUuid")
            self.token = "InFraReD=" + request.cookies.get("InFraReD")
        else:
            raise Exception("Failed to login to infrared by returning code of {}".format(request.status_code))
    
    def export_to_json(self):
        return {
            "uuid": self.uuid,
            "token": self.token,
        }
    # deletes all projects for the infrared user
    def delete_all_projects(self):
        for project_uuid in self.get_projects_uuids():
            print(project_uuid, "deleted")
            make_query(wind.queries.delete_project_query(self.uuid, project_uuid), self)

    # deletes all projects belonging to a city_pyo_user
    def delete_all_projects_for_city_pyo_user(self, city_pyo_user):
        for project_uuid, project in self.all_projects.items():
            if city_pyo_user in  project["projectName"]:
                print(project_uuid, "deleted")
                make_query(wind.queries.delete_project_query(self.uuid, project_uuid), self)

        # update all projects variable
        self.all_projects = self.get_all_projects() 


    # gets all the user's projects
    def get_all_projects(self):
        all_projects = make_query(wind.queries.get_projects_query(self.uuid), self)

        try:
            projects = get_value(
                all_projects,
                ["data", "getProjectsByUserUuid", "infraredSchema", "clients", self.uuid, "projects"]
            )
        except KeyError:
            print("no projects for user")
            return {}

        return projects

    # gets all the user's projects
    def get_projects_uuids(self):
        all_projects = self.get_all_projects()

        return all_projects.keys()

    # the root snapshot of the infrared project will be used to create buildings and perform analysis
    def get_root_snapshot_id_for_project_uuid(self, project_uuid):
        graph_snapshots_path = ["data", "getSnapshotsByProjectUuid", "infraredSchema", "clients", self.uuid,
                                "projects", project_uuid, "snapshots"]
        snapshot = make_query(wind.queries.get_snapshot_query(project_uuid), self)

        snapshot_uuid = list(get_value(snapshot, graph_snapshots_path).keys())[0]

        if not snapshot_uuid:
            print("could not get snapshot uuid")
            exit()

        return snapshot_uuid

    # infrared needs any request to be performed by user at least 1 per hour to keep account alive
    def keep_alive_ping(self):
        self.get_projects_uuids()

"""
# TODO move to 1 single file
# make query to infrared api
def make_query(query, token_cookie):
    ""
        Make query response
        auth token needs to be send as cookie
    ""
    # print(query)

    # AIT requested a sleep between the requests. To let their servers breath a bit.
    # time.sleep(0.5)

    request = requests.post(os.getenv("INFRARED_URL") + '/api', json={'query': query}, headers={'Cookie': token_cookie, 'origin': os.getenv('INFRARED_URL')})
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Query failed to run by returning code of {}. {}".format(request.status_code, query))
"""

# gets a values from a nested object
def get_value(data, path):
    for prop in path:
        if len(prop) == 0:
            continue
        if prop.isdigit():
            prop = int(prop)
        data = data[prop]
    return data

