FROM python:3.5

ENV BASE_DIR /usr/local
ENV APP_DIR $BASE_DIR/app
ENV VENV_DIR $BASE_DIR/venv

RUN adduser --system --disabled-login docker \
 && mkdir -p "$BASE_DIR" "$APP_DIR" "$VENV_DIR" \
 && chown -R docker:nogroup "$BASE_DIR" "$APP_DIR" "$VENV_DIR"

USER docker

# Only copy and install requirements to improve caching between builds
COPY --chown=docker:nogroup ./requirements $APP_DIR/requirements
RUN python3 -m venv $VENV_DIR \
 && "$VENV_DIR/bin/pip3" install -r "$APP_DIR/requirements/production.txt"

# Enable the virtual environment manually
ENV VIRTUAL_ENV "$VENV_DIR"
ENV PATH "$VENV_DIR/bin:$PATH"

# Finally, copy all the project files
COPY --chown=docker:nogroup . $APP_DIR
# Pre-compile .py files to improve start-up speed
RUN "$VENV_DIR/bin/python3" -m compileall "$APP_DIR" "$VENV_DIR"

WORKDIR $APP_DIR/src

ENTRYPOINT "$VENV_DIR/bin/python3"
