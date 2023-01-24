FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN pip install -r wind/requirements.txt

CMD ["bash", "entrypoint.sh"]
