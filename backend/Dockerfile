# Koyala API image. Build from the backend/ directory:
#   docker build -t koyala-api backend
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY koyala ./koyala
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 koyala
COPY --from=build /install /usr/local
USER koyala
WORKDIR /home/koyala
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "koyala.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
