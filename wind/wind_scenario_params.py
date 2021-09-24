from wind.cityPyo import CityPyo


class WindScenarioParams:
    def __init__(self, request_json: dict):
        self.wind_speed = request_json["wind_speed"]
        self.wind_direction = request_json["wind_direction"]
        self.hash = request_json["hash"]
        self.result_format = request_json["result_format"]
        
        try:
            self.city_pyo_user_id = request_json["city_pyo_user"]
        except:
            raise Exception("Please specify cityPyo user")
    
