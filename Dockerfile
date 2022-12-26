
FROM python:3.9

WORKDIR /app

COPY . .

RUN pip3 install Cython && pip3 install -r requirements.txt


CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
