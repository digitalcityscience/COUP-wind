#!/bin/bash
# PLEASE SPECIFY YOUR AUTH TOKEN AND CITYPYO USER ID BELOW

curl --location --request POST 'http://localhost:5001/trigger_calculation' \
--header 'Content-Type: application/json' \
--header 'Authorization: Basic WU9VUl9JRDpZT1VSX1BBU1NXT1JE' \
--data-raw '{
   "wind_speed": 19, "wind_direction": 24, "result_format": "geojson",
   "city_pyo_user": "YOUR_CITY_PYO_USERID"
}'
