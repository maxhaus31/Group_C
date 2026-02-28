from app import ProjectData


def main() -> None:
	"""Run project data setup and print a short summary."""
	project_data = ProjectData()
	print("Project data initialized successfully.")
	print(f"Loaded raw datasets: {list(project_data.raw_datasets.keys())}")
	print(f"Loaded merged datasets: {list(project_data.merged_datasets.keys())}")


if __name__ == "__main__":
	main()

