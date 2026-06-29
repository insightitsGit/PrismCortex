# PrismCortex — single image, two roles (ROLE=server | driver).
FROM python:3.12-slim

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 \
    PIP_PROGRESS_BAR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    PYTHONUNBUFFERED=1 \
    PRISMCORTEX_DATA=/data \
    PORT=8080

COPY pyproject.toml README.md LICENSE ./
COPY prismcortex ./prismcortex
COPY benchmarks ./benchmarks
COPY docker/entrypoint.sh ./entrypoint.sh

# Self-contained: core + the full Prism stack (PrismLang projection, PrismResonance
# wavepacket memory, PrismLib cache) + real Gemini + the web server. No torch — PrismLang
# uses an ONNX MiniLM via onnxruntime. PRISMCORTEX_BACKEND selects lite vs prism at runtime.
RUN pip install . prismlib prismlang prismresonance google-genai "fastapi>=0.110" "uvicorn[standard]>=0.27" \
    && mkdir -p /data \
    && chmod +x entrypoint.sh \
    && python -c "from prismlang import PrismProjector, TaxonomyConfig, Category; \
PrismProjector(TaxonomyConfig([Category('g','General',['a','the','is'])]), 'warm').project('bake the onnx MiniLM encoder into the image')"

EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
