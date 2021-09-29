import json
import hashlib

class WindScenarioParams:  # TODO rename in calculation Params 
    def __init__(self, request_json: dict):
        self.wind_speed = request_json["wind_speed"]
        self.wind_direction = request_json["wind_direction"]
        self.result_type = "wind" # TODO allow for solar, ..

        """ try:
            self.city_pyo_user_id = request_json["city_pyo_user"]
        except:
            raise Exception("Please specify cityPyo user")
        """

    def get_calculation_settings(self):
        return {
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "result_type": self.result_type,
            }

    """ def create_hash(self):
        dict_string = json.dumps(
            self.get_calculation_settings(),
            sort_keys=True
        )
        hash = hashlib.md5(dict_string.encode())

        return hash.hexdigest()
 """