#!/bin/bash

docker stop windfred_i
docker rm windfred_i
docker build -t=windfred . --no-cache
docker run -d \
        --name windfred_i \
        --restart always \
        windfred

docker logs -f windfred_i