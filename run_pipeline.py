"""
Entry point — run from the project root:

    python run_pipeline.py migratedImages_gbi_partNumber_CTNAPAsani_fitment_sample_10000.ndjson --output-dir sample_output
    python run_pipeline.py input.ndjson --output-dir output --locale en-us
"""
from pipeline.run import main

if __name__ == "__main__":
    main()
