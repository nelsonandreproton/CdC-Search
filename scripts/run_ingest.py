#!/usr/bin/env python3
"""Entrypoint do pipeline diário de recolha.

Uso:
    python -m scripts.run_ingest

É isto que o cron invoca 1×/dia. Imprime um resumo e devolve código de saída
diferente de 0 em caso de erro (útil para monitorização).
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> int:
    from app.ingest.pipeline import run_pipeline

    run = run_pipeline()
    print("=" * 60)
    print(f"Estado: {run.status}")
    print(f"Novas: {run.new_count} | Atualizadas: {run.updated_count} | Vistas: {run.seen_count}")
    print(run.log)
    print("=" * 60)
    return 0 if run.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
