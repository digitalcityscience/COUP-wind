class ScenarioParams:
    def __init__(self, scenario_json: dict, result_type=None):
        try:
            self.wind_speed = scenario_json["wind_speed"]
            self.wind_direction = scenario_json["wind_direction"]
            self.result_type = scenario_json["result_type"]
        except KeyError as e:
            self.result_type = result_type
        
        if not self.result_type:
            raise Exception("Need to specify result type for calculation, can be wind, solar or sun")


    def export_to_json(self):
        if self.result_type == "wind":
            return {
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "result_type": self.result_type,
            }
        
        # solar and sun have no calculation settings like wind speed
        return {
            "result_type": self.result_type,
        }
   