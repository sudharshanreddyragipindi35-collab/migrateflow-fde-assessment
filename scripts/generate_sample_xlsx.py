from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "sample_data" / "employee_master.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Employee Master"
    sheet.append(["Worker ID", "Legal First", "Legal Last", "Corporate Email", "Hire Date", "Dept", "Employment Status"])
    sheet.append(["EM201", "Lena", "Kim", "lena.kim@example.test", "2021-06-14", "Operations", "Active"])
    sheet.append([202, "Omar", "Ali", "omar.ali@example.test", "2020-02-29", "Engineering", "Inactive"])
    sheet.append(["EM203", "Inez", "Garcia", "inez.garcia@example.test", None, "Support", "Active"])
    workbook.save(output)


if __name__ == "__main__":
    main()

