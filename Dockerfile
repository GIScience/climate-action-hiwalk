FROM condaforge/mambaforge:23.1.0-4 AS build

COPY environment_deploy.yaml environment.yaml

RUN --mount=type=secret,id=CI_JOB_TOKEN \
    export CI_JOB_TOKEN=$(cat /run/secrets/CI_JOB_TOKEN) && \
    mamba env create -f environment.yaml && \
    mamba install -c conda-forge conda-pack && \
    conda-pack -f --ignore-missing-files -n ca-plugin -o /tmp/env.tar && \
    mkdir /venv && \
    cd /venv && \
    tar xf /tmp/env.tar && \
    rm /tmp/env.tar  && \
    /venv/bin/conda-unpack && \
    mamba clean --all --yes

FROM python:3.11.5-bookworm as runtime

ENV PACKAGE_NAME='plugin_blueprint'

WORKDIR /ca-plugin
COPY --from=build /venv /ca-plugin/venv

COPY $PACKAGE_NAME $PACKAGE_NAME
COPY resources resources
COPY conf conf

ENV PYTHONPATH "${PYTHONPATH}:/ca-plugin/${PACKAGE_NAME}"

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /ca-plugin/venv/bin/activate && \
           python ${PACKAGE_NAME}/plugin.py
