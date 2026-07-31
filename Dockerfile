FROM python:3.13.5-bookworm

ARG CI_COMMIT_SHORT_SHA

ENV PACKAGE_NAME='walkability'

RUN useradd -ms /bin/bash plugin
USER plugin
ENV WD=/home/plugin
WORKDIR $WD

ENV POETRY_HOME="$WD/.cache/poetry"

RUN python3 -m venv $POETRY_HOME &&\
    $POETRY_HOME/bin/pip install poetry==2.*


ENV PATH="$PATH:$POETRY_HOME/bin"


COPY pyproject.toml poetry.lock ./
RUN poetry install --no-ansi --no-interaction --without dev,test --no-root

COPY $PACKAGE_NAME $PACKAGE_NAME
COPY resources resources
COPY README.md ./README.md

RUN if [[ -n "${CI_COMMIT_SHORT_SHA}" ]]; then sed -E -i "s/^(version *= *\"[^+]*)\"/\\1+${CI_COMMIT_SHORT_SHA}\"/" pyproject.toml; fi;

RUN poetry install --no-ansi --no-interaction --only-root

ENTRYPOINT ["poetry", "run", "plugin"]
CMD ["start"]

