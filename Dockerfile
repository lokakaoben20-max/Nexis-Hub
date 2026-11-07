# Image unique de Nexis Hub : backend, Mini App, bot, tâches planifiées et
# migrations partagent le même code. Le rôle se choisit au lancement :
#   docker run <image> backend | miniapp | bot | webhook-setup | migration
#                      | tache <nom> | planificateur | controle-registre
# Voir docker/lancer.sh.

# Python 3.13 slim (Debian bookworm), épinglé par empreinte : la même base à
# chaque construction. Mettre à jour par PR (tag + empreinte).
ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72

FROM ${PYTHON_IMAGE} AS dependances
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt /tmp/requirements.txt
# Versions figées et empreintes vérifiées (requirements.txt) ; roues
# binaires uniquement : aucun compilateur dans l'image.
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --require-hashes --only-binary=:all: -r /tmp/requirements.txt

FROM ${PYTHON_IMAGE}
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production
RUN groupadd --system --gid 10001 nexis \
 && useradd --system --uid 10001 --gid nexis --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin nexis
COPY --from=dependances /opt/venv /opt/venv
WORKDIR /app
# Code en lecture seule pour le processus : il appartient à root, le
# processus tourne en `nexis`. Rien n'est écrit à côté du code.
COPY --chown=root:root --chmod=a-w . /app
USER nexis:nexis
ENTRYPOINT ["/bin/sh", "/app/docker/lancer.sh"]
CMD ["backend"]
