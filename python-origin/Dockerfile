FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=3000
WORKDIR /app
COPY requirements.txt ./
RUN python --version && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check
COPY . .
RUN python -m compileall -q . \
    && useradd --create-home --uid 10001 movieapi
USER movieapi
EXPOSE 3000
CMD ["python", "local.py"]
