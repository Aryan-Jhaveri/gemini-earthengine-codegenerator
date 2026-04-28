.PHONY: stac-index test-mulerouter install

# Rebuild the EE STAC dataset index (run weekly or after adding new datasets)
stac-index:
	python scripts/build_stac_index.py

stac-index-dry:
	python scripts/build_stac_index.py --dry-run

# Smoke-test the MuleRouter Qwen integration
test-mulerouter:
	python scripts/test_mulerouter.py

# Install Python dependencies
install:
	pip install -r requirements.txt
