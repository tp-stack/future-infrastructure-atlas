FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY atlas/ atlas/
COPY backend/main.py .

ENV PYTHONPATH=/app
ENV SITE_SELECTION_STORAGE_DIR=/app/data/reports/site_selection

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
