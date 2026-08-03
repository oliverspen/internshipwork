FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
	&& apt-get install -y --no-install-recommends tk tcl \
	&& rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app
RUN mkdir /app/results

RUN chown -R 1000:1000 /app/results

ENV UV_NO_CACHE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg

RUN uv sync --frozen --no-dev --no-editable

USER 1000

EXPOSE 8000

ENTRYPOINT ["uv", "run", "--frozen", "python", "main.py"]
