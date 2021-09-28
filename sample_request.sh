#!/bin/bash

curl -X POST  http://localhost:5003/windtask -H 'Content-type: application/json' \
    -d '{ "city_pyo_user": "", "wind_speed": 25, "wind_direction": 258, "result_format": "geojson", "custom_roi": [], "hash": "test_local_2", "city_pyo_user": "90af2ace6cb38ae1588547c6c20dcb36" }'
