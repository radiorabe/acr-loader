FROM ghcr.io/radiorabe/s2i-python:3.1.0 AS build

COPY --chown=1001:0 ./ /opt/app-root/src/

RUN    python3.12 -mbuild


FROM ghcr.io/radiorabe/python-minimal:3.1.0 AS app

COPY --from=build /opt/app-root/src/dist/*.whl /tmp/dist/

RUN    microdnf install -y \
         python3.12-pip \
    && python3.12 -mpip --no-cache-dir install /tmp/dist/*.whl \
    && microdnf remove -y \
         python3.12-pip \
         python3.12-setuptools \
    && microdnf clean all \
    && rm -rf /tmp/dist/

USER nobody

CMD ["acrloader"]
