ARG PYTHON_VER=3.11

FROM python:${PYTHON_VER}-slim

# Install all OS package upgrades and dependencies needed to run Nautobot in production
# hadolint ignore=DL3005,DL3008,DL3013
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y git media-types curl libxml2 libmariadb3 openssl && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --upgrade pip wheel

RUN pip install --upgrade pip

RUN curl -sSL https://install.python-poetry.org -o /tmp/install-poetry.py && \
    python /tmp/install-poetry.py && \
    rm -f /tmp/install-poetry.py

# Add poetry install location to the $PATH
ENV PATH="${PATH}:/root/.local/bin"

WORKDIR /local
COPY pyproject.toml poetry.lock /local/

RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --no-root

# Do not break dependency caching before installing project
COPY . .
# Poetry 2.x reports installing the root project but does not when
# virtualenvs.create is false, so install it with pip; deps are already present.
RUN pip install --no-deps --no-cache-dir .
