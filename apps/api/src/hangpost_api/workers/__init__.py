"""Background workers (Arq, Redis-backed).

Phase 1+ jobs land here: profile embedding, notification fan-out, and the
nightly outcome ETL + retrain that closes the ML loop (CLAUDE.md §5).
"""
