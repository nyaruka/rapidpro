FROM "mcr.microsoft.com/devcontainers/typescript-node:1-20-bullseye"

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV CHROME_PATH=/usr/bin/chromium
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install chromium fonts-noto-color-emoji dnsutils curl -y --no-install-recommends -qq

# bun manages JS dependencies and runs package scripts.
# Pinned to match the version bun.lock was generated with (CI uses
# --frozen-lockfile); bump this deliberately alongside the lockfile.
# Replaces the old corepack packageManager pin.
RUN npm install -g bun@1.3.14

USER node
