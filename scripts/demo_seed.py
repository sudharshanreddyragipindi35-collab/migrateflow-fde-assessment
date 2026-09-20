from pathlib import Path
FILES = ["employees_india.csv", "employee_master.xlsx", "new_joiners.csv"]
if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "sample_data"
    for name in FILES:
        path = root / name
        if not path.exists(): raise SystemExit(f"Missing demo file: {path}")
        print(path)
