"""Allow `python -m peer_benchmarking.ingest 2025Q4 --zip ...`."""

from peer_benchmarking.ingest.loader import main

if __name__ == "__main__":
    raise SystemExit(main())
