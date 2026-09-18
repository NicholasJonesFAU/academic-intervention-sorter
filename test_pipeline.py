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
from processors.group_matcher import GroupMatcher, GroupDefinition
from utils.logging_utils import setup_logger, QALog
from utils.config import (
    CAMPUS_76_LOW_TAB,
    CAMPUS_76_HIGH_TAB,
    UNMATCHED_LOW_TAB,
    UNMATCHED_HIGH_TAB,
)

logger = setup_logger("intervention_sorter")

SAMPLE_DIR = Path(__file__).parent / "sample_data"


def _assert_campus76_routing() -> None:
    """Campus 76 tries control lists first, then splits by earned credits at 45."""
    import pandas as pd

    matcher = GroupMatcher(QALog())
    matcher._groups = [
        GroupDefinition(
            tab_name="Athletes",
            filename="athletes.xlsx",
            student_ids={"Z1"},
            safe_tab_name="Athletes",
        ),
    ]
    students = pd.DataFrame({
        "Student ID": ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"],
        "Student Name": ["A", "B", "C", "D", "E", "F"],
        "Campus": ["76", 76.0, "76", "01", "76", "76"],
        "Total Earned Credits": [20, 45, 46, 10, "", 90],
        "Risk Course Count": [1, 2, 3, 1, 1, 4],
        "Absences": [0, 0, 0, 0, 0, 0],
    })
    result = matcher.match(students)

    assert "Z1" in set(result["Athletes"]["Student ID"]), (
        "Campus 76 student on a control list should stay on that list"
    )
    low_ids = set(result[CAMPUS_76_LOW_TAB]["Student ID"])
    high_ids = set(result[CAMPUS_76_HIGH_TAB]["Student ID"])
    risk_low = set(result[UNMATCHED_LOW_TAB]["Student ID"])
    risk_high = set(result[UNMATCHED_HIGH_TAB]["Student ID"])

    assert low_ids == {"Z2", "Z5"}, f"45-and-under tab mismatch: {low_ids}"
    assert high_ids == {"Z3", "Z6"}, f"Over-45 tab mismatch: {high_ids}"
    assert risk_low == {"Z4"}, f"Non-76 unmatched should stay in Risk_1_2: {risk_low}"
    assert not risk_high, f"No campus 76 student should land in Risk_3_Plus: {risk_high}"
    print("  Campus 76 routing: OK")


def main():
    print("=" * 60)
    print("Academic Intervention Sorter - Pipeline Test")
    print("=" * 60)

    print("\n[0] Campus 76 routing:")
    _assert_campus76_routing()

    inputs = PipelineInputs(
        progress_report=SAMPLE_DIR / "progress_report_sample.csv",
        contact_report=SAMPLE_DIR / "contact_report_sample.xlsx",
        registration_report=SAMPLE_DIR / "registration_report_sample.xlsx",
        first_gen_list=SAMPLE_DIR / "first_gen_sample.csv",
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
