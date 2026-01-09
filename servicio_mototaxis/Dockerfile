FROM python:3.11-slim

WORKDIR /usr/src/app/servicio_mototaxis

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

EXPOSE 5002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5002"]