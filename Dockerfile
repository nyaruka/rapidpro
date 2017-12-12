FROM ubuntu:16.04

ENV PROJECT_DIR=/project

RUN mkdir $PROJECT_DIR \
    && groupadd -r app -g 1000 \
    && useradd -r -u 1000 -g app -d $PROJECT_DIR -s /sbin/nologin -c "Docker image user" app


WORKDIR $PROJECT_DIR
ADD . $PROJECT_DIR

ENV PYTHONUNBUFFERED 1
ENV NVM_DIR=/opt/nvm NODE_VERSION=v6.11.5

RUN apt-get update -y \
    && apt-get install --assume-yes --quiet locales \
    && locale-gen en_US.UTF-8 \
    && export LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8 \
    && apt-get install --assume-yes --quiet build-essential python-pip python-dev libssl-dev libffi-dev python-gdal curl python-setuptools libmagic1 postgresql-client-9.5 \
    && curl -o- https://raw.githubusercontent.com/creationix/nvm/v0.33.6/install.sh | bash \
    && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" \
    && nvm install $NODE_VERSION \
    && npm install -g less@2.7.1 coffeescript@^1.9.3 bower@^1.7.9 \
    && npm install \
    && mv node_modules /opt \
    && pip install --no-cache-dir -r /project/pip-freeze.txt \
    && rm -r /var/lib/apt/lists/*

# 'hardcode' node path
ENV NODE_PATH=$NVM_DIR/versions/node/$NODE_VERSION/lib/node_modules:/opt/node_modules
ENV PATH=$NVM_DIR/versions/node/$NODE_VERSION/bin:/opt/node_modules/.bin:$PATH

ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

USER app
