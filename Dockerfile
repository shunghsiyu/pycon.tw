FROM python:3.6

# NodeJS's version is not pinned becuase nodesource only serve the latest
# version.
ENV YARN_VERSION 1.15.2-1
ENV PYTHONUNBUFFERED 1
ENV BASE_DIR /usr/local
ENV APP_DIR $BASE_DIR/app
ENV VENV_DIR $BASE_DIR/venv

# Install Node and Yarn from upstream
RUN curl -sS https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - \
 && echo 'deb http://deb.nodesource.com/node_8.x stretch main' | tee /etc/apt/sources.list.d/nodesource.list \
 && curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - \
 && echo 'deb http://dl.yarnpkg.com/debian/ stable main' | tee /etc/apt/sources.list.d/yarn.list \
 && apt-get update \
 && apt-get install -y nodejs yarn=$YARN_VERSION
RUN adduser --system --disabled-login docker \
 && mkdir -p "$BASE_DIR" "$APP_DIR" "$APP_DIR/src/assets" "$APP_DIR/src/media" "$VENV_DIR" \
 && chown -R docker:nogroup "$BASE_DIR" "$APP_DIR" "$VENV_DIR"

USER docker
WORKDIR $APP_DIR

# Only copy and install requirements to improve caching between builds
COPY --chown=docker:nogroup ./requirements $APP_DIR/requirements
RUN python3 -m venv $VENV_DIR \
 && "$VENV_DIR/bin/pip3" install -r "$APP_DIR/requirements/production.txt" \
 # Pre-compile .py files in standard library and venv library to improve
 # start-up speed.
 && "$VENV_DIR/bin/python3" -m compileall \
 # dbfpy contains a file using Python 2 syntax, and needs to be ignored during
 # compilation.
 && "$VENV_DIR/bin/python3" -m compileall "$VENV_DIR/lib" -x 'dbfpy/dbfnew\.py'
COPY --chown=docker:nogroup ./package.json $APP_DIR/package.json
COPY --chown=docker:nogroup ./yarn.lock $APP_DIR/yarn.lock
RUN yarn install --dev --frozen-lockfile

# Enable the virtual environment manually
ENV VIRTUAL_ENV "$VENV_DIR"
ENV PATH "$VENV_DIR/bin:$PATH"
WORKDIR $APP_DIR/src

# Pre-compile .py files in project to improve start-up speed
COPY --chown=docker:nogroup ./src $APP_DIR/src
RUN "$VENV_DIR/bin/python3" -m compileall "$APP_DIR/src"

# Finally, copy all the project files
COPY --chown=docker:nogroup . $APP_DIR

VOLUME $APP_DIR/src/media
EXPOSE 8000
CMD ["uwsgi", "--http-socket", ":8000", "--master", \
     "--hook-master-start", "unix_signal:15 gracefully_kill_them_all", \
     "--static-map", "/static=assets", "--static-map", "/media=media", \
     "--mount", "/2018=pycontw2016/wsgi.py", "--manage-script-name", \
     "--offload-threads", "2"]
