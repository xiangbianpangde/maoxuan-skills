.PHONY: sync index evidence benchmark-data benchmark-dry check all
sync:
	python3 scripts/sync_upstreams.py
index:
	python3 retrieval/build_index.py
evidence:
	python3 scripts/build_source_manifest.py
	python3 scripts/build_evidence_map.py
	python3 eval/evidence_coverage.py
benchmark-data:
	python3 eval/build_atomic_benchmark.py
benchmark-dry: benchmark-data
	python3 eval/run_router_benchmark.py --dry-run
check:
	python3 eval/run_static_checks.py
all: sync benchmark-data index evidence check
