#!/bin/bash

curl -X POST  http://localhost:5000/windtask -H 'Content-type: application/json' \
    -d '{ "city_pyo_user": "", "wind_speed": 25, "wind_direction": 270, "result_format": "geojson", "custom_roi": [], "hash": "newnewdfasdfranew" }'
