#!/bin/bash
# PLEASE SPECIFY YOUR AUTH TOKEN AND CITYPYO USER ID BELOW

curl --location --request POST 'http://localhost:5001/trigger_calculation' \
--header 'Content-Type: application/json' \
--header 'Authorization: Basic WU9VUl9JRDpZT1VSX1BBU1NXT1JE' \
--data-raw '{
   "wind_speed": 23, "wind_direction": 40, "result_format": "geojson",
   "city_pyo_user": "10a1abf703145e1186b65293b8337680"
}'
