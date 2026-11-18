FROM ghcr.io/mamba-org/micromamba:2.9.0-ubuntu24.04

LABEL org.opencontainers.image.title="Lemon Balm Corrosion Reproducibility"
LABEL org.opencontainers.image.description="Headless open-source workflow for corrosion-inhibitor computational study reproduction"

USER root
RUN apt-get update && apt-get install -y --no-install-recommends bash git ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
USER $MAMBA_USER
RUN micromamba install --strict-channel-priority -y -n base -f /tmp/environment.yml && micromamba clean --all --yes

WORKDIR /work
COPY --chown=$MAMBA_USER:$MAMBA_USER . /work
ENV PATH="/opt/conda/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
# Fail the build if either engine cannot load or execute a minimal calculation.
RUN ZZ_BALM_REQUIRE_ENGINES=1 micromamba run -n base python -m pytest -q tests
ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["audit"]
