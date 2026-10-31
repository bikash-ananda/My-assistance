FROM python:3.14.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /srv/services/api
COPY services/api/requirements.txt /srv/services/api/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY services/api/app /srv/services/api/app
RUN mkdir -p /data && chown -R 10001:10001 /data
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
