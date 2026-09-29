import os
import shutil
import subprocess
from pathlib import Path

PARQUET_DIR = r"C:\Temp\imagery\class_test\processed\sam-labels\parquet"
INDEX_FILE = "parquet_index.gpkg"


def flatten_parquet_files(directory: str | Path) -> int:
	root = Path(directory)
	moved_count = 0

	for source_dir in root.iterdir():
		if not source_dir.is_dir():
			continue

		parquet_files = list(source_dir.glob("*.parquet"))
		if not parquet_files:
			continue

		for source_file in parquet_files:
			destination = root / source_file.name
			os.replace(source_file, destination)
			moved_count += 1

		shutil.rmtree(source_dir)

	return moved_count


def create_vector_index(
	directory: str | Path, output_name: str = INDEX_FILE
) -> Path:
	root = Path(directory)
	parquet_files = sorted(root.glob("*.parquet"))
	if not parquet_files:
		raise FileNotFoundError(f"No parquet files found in {root}")

	ogrtindex = shutil.which("ogrtindex")
	if ogrtindex is None:
		raise FileNotFoundError("ogrtindex is not available on PATH")

	proj_data = Path(ogrtindex).parent.parent / "share" / "proj"
	environment = os.environ.copy()
	if proj_data.is_dir():
		environment["PROJ_DATA"] = str(proj_data)
		environment["PROJ_LIB"] = str(proj_data)

	output_path = root / output_name
	output_path.unlink(missing_ok=True)
	command = [
		ogrtindex,
		"-of",
		"GPKG",
		str(output_path),
		*[str(parquet_file) for parquet_file in parquet_files],
	]
	subprocess.run(command, check=True, env=environment)
	return output_path


def main() -> None:
	moved_count = flatten_parquet_files(PARQUET_DIR)
	print(f"Moved {moved_count} parquet files into {PARQUET_DIR}")
	output_path = create_vector_index(PARQUET_DIR)
	print(f"Created vector index from parquet files: {output_path}")


if __name__ == "__main__":
	main()