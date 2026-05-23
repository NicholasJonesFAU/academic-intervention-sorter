"""
test_pipeline.py — Headless test runner for the pipeline (no GUI required).

Usage:
    python test_pipeline.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from processors.pipeline_controller import PipelineController, PipelineInputs
from utils.logging_utils import setup_logger

logger = setup_logger("intervention_sorter")

TEST_DIR = Path(__file__).parent / "test_data"
OUTPUT_DIR = Path(__file__).parent / "output"


def main():
    print("=" * 60)
    print("Academic Intervention Sorter — Pipeline Test")
    print("=" * 60)

    inputs = PipelineInputs(
        progress_report=TEST_DIR / "progress_report.xlsx",
        contact_report=TEST_DIR / "contact_report.xlsx",
        control_file=TEST_DIR / "control.txt",
        group_dir=TEST_DIR / "groups",
        output_dir=OUTPUT_DIR,
    )

    def on_progress(msg: str):
        print(f"  → {msg}")

    controller = PipelineController(progress_callback=on_progress)

    # Validation pass
    print("\n[1] Validation-only run:")
    val_result = controller.validate_only(inputs)
    status = "✅ PASSED" if val_result.success else "❌ FAILED"
    print(f"    Status: {status}")
    if val_result.errors:
        for e in val_result.errors:
            print(f"    ERROR: {e}")
    for w in val_result.warnings:
        print(f"    INFO: {w}")

    # Full run
    print("\n[2] Full pipeline run:")
    result = controller.run(inputs)

    if result.success:
        print(f"\n✅ SUCCESS")
        print(result.message)
        print(f"\nOutput: {result.output_path}")
        print("\nMetrics:")
        for k, v in result.metrics.items():
            print(f"  {k}: {v}")
    else:
        print(f"\n❌ FAILED: {result.message}")
        for e in result.errors:
            print(f"  ERROR: {e}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
