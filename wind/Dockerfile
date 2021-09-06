FROM python

RUN mkdir app

# install python dependancies
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# get the scripts
COPY *.py /app/

# get the config files with login credentials
COPY cityPyo.json /app/
COPY infrared.json /app/

# get the project area geojson
COPY project_area_utm.geojson /app/


# work it
WORKDIR /app
CMD [ "python", "/app/main.py" ]