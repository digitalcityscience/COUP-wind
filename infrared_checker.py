import os
import requests
import json



if __name__ == "__main__":
    print("checking first time")
    
    api_url = os.getenv("WIND_API_URL")
    check_projects_route = 'check_projects_for_user'
    headers = {
    'Content-type': 'application/json',
    }

    for cityPyo_user in os.getenv("CITYPYO_USERS"):
        data = {"city_pyo_user": cityPyo_user}
    
        response = requests.post(url=api_url + check_projects_route, headers=headers, data=json.dumps(data))
    
        if not (response.status_code == 200):
            print(response)

    
    
    
    
    
    
    
    
    
    
    

    
    
    
    

    


