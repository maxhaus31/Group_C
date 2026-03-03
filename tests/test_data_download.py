import os
from app.data_download import download_datasets, DOWNLOADS_DIR, DATASETS

def test_downloads_dir_exists():
    """
    Test that download_datasets() creates the downloads directory.
    Verifies DOWNLOADS_DIR exists after running the download function.
    """
    download_datasets()
    assert os.path.exists(DOWNLOADS_DIR)

def test_all_files_downloaded(tmp_path):
    """
    Test creates all expected files.
    Verifies one file per DATASETS entry is created with correct extension (.csv / .zip).
    """
    download_datasets(downloads_dir=tmp_path)
    for name, url in DATASETS.items():
        extension = ".zip" if url.endswith(".zip") else ".csv"
        expected_file = os.path.join(tmp_path, f"{name}{extension}")
        assert os.path.exists(expected_file), f"Missing file: {name}{extension}"

def test_files_not_empty():
    """
    Test all downloaded files have non-zero size.
    Verifies downloads are complete
    """
    download_datasets()
    for name, url in DATASETS.items():
        extension = ".zip" if url.endswith(".zip") else ".csv"
        file_path = os.path.join(DOWNLOADS_DIR, f"{name}{extension}")
        assert os.path.getsize(file_path) > 0, f"Empty file: {name}{extension}"

