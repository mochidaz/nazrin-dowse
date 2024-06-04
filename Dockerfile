FROM python:3.10 as builder
ARG PYTHONUNBUFFERED=1
COPY requirements.txt /
RUN pip wheel -r /requirements.txt  --wheel-dir /usr/src/app/wheels

FROM python:3.10 as runner
COPY --from=builder /usr/src/app/wheels  /wheels/
RUN set -ex; \
    pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/*; \
    rm -rf /wheels/; \
    mkdir -p /app; \
    useradd --shell /bin/false app -d /app; \
    chown app:app /app
WORKDIR /app
COPY --chown=app:app . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

USER app
ENTRYPOINT ["gunicorn"]
CMD ["main:app", "--bind", "0.0.0.0:8000", "--log-level=INFO", "--timeout=120"]