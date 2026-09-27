.PHONY: sync index evidence check all
sync:
	python3 scripts/sync_upstreams.py
index:
	python3 retrieval/build_index.py
evidence:
	python3 scripts/build_source_manifest.py
	python3 scripts/build_evidence_map.py
check:
	python3 eval/run_static_checks.py
all: sync index evidence check
