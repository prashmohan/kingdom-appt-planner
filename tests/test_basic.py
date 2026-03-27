import os
import shutil
import tempfile
from flask import Flask
from app import generate_slot_labels, database

def test_generate_slot_labels():
    labels = generate_slot_labels()
    assert len(labels) == 49
    # Check slot 0 (23:45-00:15)
    assert labels[0] == "23:45-00:15"
    # Check slot 1 (00:15-00:45)
    assert labels[1] == "00:15-00:45"
    # Check wrap around at the end
    assert labels[48].endswith("23:45") or "23:45" in labels[48]

def test_init_db_creates_directory():
    # Create a path in a new temp directory
    tmpdir = tempfile.mkdtemp()
    new_dir = os.path.join(tmpdir, "subdir")
    db_path = os.path.join(new_dir, "test.db")
    
    # Ensure subdir doesn't exist
    assert not os.path.exists(new_dir)
    
    app = Flask(__name__)
    database.DATABASE_PATH = db_path
    database.init_app(app)
    
    # Verify subdir was created
    assert os.path.exists(new_dir)
    assert os.path.exists(db_path)
    
    # Cleanup
    shutil.rmtree(tmpdir)
