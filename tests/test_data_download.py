import os
from app.data_download import download_datasets, DOWNLOADS_DIR, DATASETS

def test_downloads_dir_exists():
    download_datasets()
    assert os.path.exists(DOWNLOADS_DIR)

def test_all_files_downloaded(tmp_path):
    download_datasets(downloads_dir=tmp_path)
    for name, url in DATASETS.items():
        extension = ".zip" if url.endswith(".zip") else ".csv"
        expected_file = os.path.join(tmp_path, f"{name}{extension}")
        assert os.path.exists(expected_file), f"Missing file: {name}{extension}"

def test_files_not_empty():
    download_datasets()
    for name, url in DATASETS.items():
        extension = ".zip" if url.endswith(".zip") else ".csv"
        file_path = os.path.join(DOWNLOADS_DIR, f"{name}{extension}")
        assert os.path.getsize(file_path) > 0, f"Empty file: {name}{extension}"

