FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app

COPY services/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY VERSION ./VERSION
COPY packages ./packages
COPY services/api/app ./app
COPY services/api/alembic ./alembic
COPY services/api/alembic.ini ./alembic.ini
COPY scripts/create_district_master.py ./scripts/create_district_master.py

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
