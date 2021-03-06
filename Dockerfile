FROM python:3.7-slim-buster

RUN apt-get update && apt-get install ffmpeg libpq-dev gcc python3-dev musl-dev -y

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY src /app/src/
RUN mkdir -p /app/cache/pledge
RUN mkdir -p /app/cache/sponsorships

WORKDIR /app
CMD ["python3", "src/main.py"]
