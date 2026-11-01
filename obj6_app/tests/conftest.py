import os, tempfile
os.environ.setdefault("DRESSME_DB", os.path.join(tempfile.mkdtemp(), "fb.db"))
