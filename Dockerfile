FROM condaforge/mambaforge:23.1.0-4 AS build

COPY environment.yaml environment.yaml

RUN --mount=type=secret,id=GIT_PROJECT_TOKEN \
    export GIT_PROJECT_TOKEN=$(cat /run/secrets/GIT_PROJECT_TOKEN) && \
    mamba env create -f environment.yaml && \
    mamba install -c conda-forge conda-pack && \
    conda-pack -f --ignore-missing-files -n ca-plugin-blueprint -o /tmp/env.tar && \
    mkdir /venv && \
    cd /venv && \
    tar xf /tmp/env.tar && \
    rm /tmp/env.tar  && \
    /venv/bin/conda-unpack && \
    mamba clean --all --yes

FROM python:3.11.5-bookworm as runtime

WORKDIR /ca-plugin-blueprint
COPY --from=build /venv /ca-plugin-blueprint/venv

COPY plugin plugin
COPY resources resources

ENV PYTHONPATH "${PYTHONPATH}:/ca-plugin-blueprint/plugin"

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /ca-plugin-blueprint/venv/bin/activate && \
           python plugin/plugin.py
