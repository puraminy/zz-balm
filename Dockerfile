FROM mambaorg/micromamba:1.5.12

LABEL org.opencontainers.image.title="Lemon Balm Corrosion Reproducibility"
LABEL org.opencontainers.image.description="Headless open-source workflow for corrosion-inhibitor computational study reproduction"

USER root
RUN apt-get update && apt-get install -y --no-install-recommends bash git ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
USER $MAMBA_USER
RUN micromamba install -y -n base -f /tmp/environment.yml && micromamba clean --all --yes

WORKDIR /work
COPY --chown=$MAMBA_USER:$MAMBA_USER . /work
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["audit"]
