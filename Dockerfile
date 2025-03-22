FROM python:3.10-slim

# Install necessary dependencies first
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf-xlib-2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    xdg-utils \
    ffmpeg \
    aria2 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

ENV CHROME_VERSION=136.0.7103.49

# Install Chrome
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mv chrome-linux64 /opt/chrome && \
    ln -s /opt/chrome/chrome /usr/bin/google-chrome && \
    rm chrome-linux64.zip

# Install specific version of ChromeDriver that's known to be stable
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf chromedriver-linux64.zip chromedriver-linux64

RUN google-chrome --version && chromedriver --version

WORKDIR /app

COPY src src
COPY api api
COPY pyproject.toml pyproject.toml

RUN pip install --upgrade pip setuptools wheel
RUN pip install -e .

CMD ["uvicorn", "api.app:app", "--workers", "8", "--host", "0.0.0.0", "--port", "8000"]