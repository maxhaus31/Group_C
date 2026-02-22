import os
from app.data_download import download_datasets, DOWNLOADS_DIR, DATASETS

def test_download_datasets():
    download_datasets()
    assert os.path.exists(DOWNLOADS_DIR)
    files = os.listdir(DOWNLOADS_DIR)
    assert len(files) == len(DATASETS)  # one file per dataset