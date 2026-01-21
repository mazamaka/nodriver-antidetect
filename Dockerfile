# nodriver-antidetect - Antidetect browser in Docker
# Base image with Chrome, Xvfb and fingerprint spoofing
FROM python:3.12-slim

LABEL maintainer="mazamaka"
LABEL description="Antidetect browser based on nodriver with fingerprint spoofing"
LABEL version="1.0.0"

# Build arguments for customization
ARG CHROME_VERSION=stable
ARG TIMEZONE=Europe/Berlin
ARG LOCALE=en_US.UTF-8
ARG LANG=en_US

# Environment variables for fingerprint customization
ENV TZ=${TIMEZONE}
ENV LANG=${LOCALE}
ENV LANGUAGE=${LANG}
ENV LC_ALL=${LOCALE}

# Display settings
ENV DISPLAY=:99
ENV DISPLAY_WIDTH=3440
ENV DISPLAY_HEIGHT=1440
ENV DISPLAY_DEPTH=24

# Antidetect settings - defaults based on mazamaka local profile
# Target: like_headless <= 31%, headless = 0%, stealth = 0%
ENV AD_TIMEZONE="Europe/Budapest"
ENV AD_LOCALE="ru"
ENV AD_SCREEN_WIDTH=3440
ENV AD_SCREEN_HEIGHT=1440
ENV AD_DEVICE_MEMORY=8
ENV AD_HARDWARE_CONCURRENCY=12
ENV AD_PLATFORM="Linux x86_64"
ENV AD_WEBGL_VENDOR="Google Inc. (NVIDIA Corporation)"
ENV AD_WEBGL_RENDERER="ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)"
ENV AD_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
ENV AD_LANGUAGES="ru,en-US,en,uk"

# Profile settings - load fingerprint from JSON file
# Set AD_PROFILE_PATH to use custom JSON profile (e.g., /profiles/custom.json)
ENV AD_PROFILE_PATH=""

# Proxy settings
ENV PROXY_URL=""

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    wget \
    curl \
    gnupg \
    ca-certificates \
    git \
    # Xvfb and display
    xvfb \
    x11-utils \
    x11-xserver-utils \
    # Fonts for proper rendering
    fonts-liberation \
    fonts-noto \
    fonts-noto-color-emoji \
    fonts-dejavu-core \
    fontconfig \
    # Chrome dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libxshmfence1 \
    # Audio (for Web Audio API fingerprint)
    pulseaudio \
    # Timezone data
    tzdata \
    # Locales
    locales \
    && rm -rf /var/lib/apt/lists/*

# Configure locales
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

# Configure timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Google Chrome
RUN mkdir -p /etc/apt/keyrings && \
    wget -q -O /etc/apt/keyrings/google-chrome.asc https://dl.google.com/linux/linux_signing_key.pub && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.asc] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-${CHROME_VERSION} && \
    rm -rf /var/lib/apt/lists/*

# Create app user (non-root for security)
RUN useradd -m -s /bin/bash browser && \
    mkdir -p /app /data && \
    chown -R browser:browser /app /data

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy antidetect module
COPY antidetect/ ./antidetect/

# Copy JSON fingerprint profiles
COPY profiles/ ./profiles/

# Copy examples
COPY examples/ ./examples/

# Copy entrypoint and utilities
COPY entrypoint.sh /entrypoint.sh
COPY scripts/ ./scripts/
RUN chmod +x /entrypoint.sh ./scripts/*.sh 2>/dev/null || true

# Switch to non-root user
USER browser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -x Xvfb > /dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-c", "print('nodriver-antidetect ready')"]
