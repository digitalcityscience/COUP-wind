#!/bin/bash

curl -X POST http://localhost:5000/grouptasks -H 'Content-type: application/json' \
    -d '{"tasks": [ { "calculation_method": "normal", "hash": "yxz123", "model_updates": [ { "outlet_id": "J_out19", "subcatchment_id": "Sub000" } ], "rain_event": { "duration": 120, "return_period": 10 } } ]}'