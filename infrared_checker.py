import os
import requests
import json
import time

def run_checks():
    for cityPyo_user in cityPyo_users:
       print("cityPyo user", cityPyo_user)
       data = {"city_pyo_user": cityPyo_user}
       response = requests.post(url=api_url + check_projects_route, headers=headers, data=json.dumps(data))
 
       if not (response.status_code == 200):
         # time out - wait a while to let projects be setup and try again
           time.sleep(600)
           response = requests.post(url=api_url + check_projects_route, headers=headers, data=json.dumps(data))
        
       elif not (response.status_code == 200):         
           # checks failed. 
           print("checks FAILED for cityPyo user, ", cityPyo_user)
           continue
    
       else:
            print("SUCCESS for cityPyo user ", cityPyo_user)
    
    return True
 

if __name__ == "__main__":
    api_url = os.getenv("WIND_API_URL")
    check_projects_route = 'check_projects_for_user'
    headers = {
    'Content-type': 'application/json',
    }

    print("posting to " , api_url + check_projects_route)

    cityPyo_users = os.getenv("CITYPYO_USERS").split(",")

    everything_ok = run_checks()

    if not everything_ok:
        print("Projects do not seem to be setup right. We should have a ")
    
    
    
    

    
    
    
    

    


