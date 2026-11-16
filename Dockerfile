FROM node:24-bookworm-slim

ENV NODE_ENV=production \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv ca-certificates libcurl4 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev

COPY . .
RUN /opt/venv/bin/pip install --no-cache-dir -r media_transport/requirements.txt

EXPOSE 3000
CMD ["npm", "start"]
