FROM python:3.8

LABEL org.opencontainers.image.authors="vinh-ngu@hotmail.com"

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN pip install -r wind/requirements.txt

# TODO enable cors for entrypoint sh
CMD ["python", "entrypoint.py"]
