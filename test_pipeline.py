"""
test_pipeline.py — Headless test runner for the pipeline (no GUI required).

Runs against the bundled demo data. Regenerate it first if it is missing:

    python generate_sample_data.py
    python test_pipeline.py

Output is deliberately plain ASCII — the default Windows console encoding
cannot print arrows or check marks and raises UnicodeEncodeError.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from processors.pipeline_controller import PipelineController, PipelineInputs
from utils.logging_utils import setup_logger

logger = setup_logger("intervention_sorter")

SAMPLE_DIR = Path(__file__).parent / "sample_data"


def main():
    print("=" * 60)
    print("Academic Intervention Sorter - Pipeline Test")
    print("=" * 60)

    inputs = PipelineInputs(
        progress_report=SAMPLE_DIR / "progress_report_sample.csv",
        contact_report=SAMPLE_DIR / "contact_report_sample.xlsx",
        registration_report=SAMPLE_DIR / "registration_report_sample.xlsx",
        control_file=SAMPLE_DIR / "group_control.txt",
        group_dir=SAMPLE_DIR / "group_files",
    )

    def on_progress(msg: str):
        print(f"  > {msg}")

    controller = PipelineController(progress_callback=on_progress)

    # Validation pass
    print("\n[1] Validation-only run:")
    val_result = controller.validate_only(inputs)
    print(f"    Status: {'PASSED' if val_result.success else 'FAILED'}")
    for e in val_result.errors:
        print(f"    ERROR: {e}")
    for w in val_result.warnings:
        print(f"    INFO: {w}")

    # Full run
    print("\n[2] Full pipeline run:")
    result = controller.run(inputs)

    if result.success:
        print("\nSUCCESS")
        print(result.message)
        print(f"\nOutput: {result.output_path}")
        if result.sas_output_path:
            print(f"SAS output: {result.sas_output_path}")
        print("\nMetrics:")
        for k, v in result.metrics.items():
            print(f"  {k}: {v}")
    else:
        print(f"\nFAILED: {result.message}")
        for e in result.errors:
            print(f"  ERROR: {e}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
