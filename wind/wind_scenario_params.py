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
            self.set_default_city_pyo_user()

        if not request_json["city_pyo_user"]:
            self.set_default_city_pyo_user()

            
    def set_default_city_pyo_user(self):
        import wind.cityPyo
        cityPyo = CityPyo()
        self.city_pyo_user_id = cityPyo.cityPyo_user_ids[0]


    
