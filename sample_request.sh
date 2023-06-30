#!/bin/bash
# PLEASE SPECIFY YOUR AUTH TOKEN AND CITYPYO USER ID BELOW


curl --location --request POST 'http://localhost:5001/trigger_calculation' \
--header 'Content-Type: application/json' \
--header 'Authorization: Basic dXNlcjpwdw==' \
--data-raw '{
   "wind_speed": 19, "wind_direction": 28, "result_format": "geojson",
   "city_pyo_user": "YOUR_USER_ID"
}'


curl --location --request POST 'http://localhost:5001/trigger_calculation_sun' \
--header 'Content-Type: application/json' \
--header 'Authorization: Basic dXNlcjpwdw==' \
--data-raw '{
   "city_pyo_user": "YOUR_USER_ID"
}'


curl --location --request GET 'http://localhost:5001/collect_results/4c66ad4e-f4a1-4675-aaa7-cc00134eba0b' \
--header 'Content-Type: application/json' \
--header 'Authorization: Basic dXNlcjpwdw==' 
