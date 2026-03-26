import pytest
from app import generate_slot_labels

def test_generate_slot_labels():
    labels = generate_slot_labels()
    assert len(labels) == 49
    # Check slot 0 (23:45-00:15)
    assert labels[0] == "23:45-00:15"
    # Check slot 1 (00:15-00:45)
    assert labels[1] == "00:15-00:45"
    # Check wrap around at the end
    assert labels[48].endswith("23:45") or "23:45" in labels[48]
