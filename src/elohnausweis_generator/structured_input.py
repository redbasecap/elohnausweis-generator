from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, TextIO

from .model import (
    Address,
    Employee,
    EmployeeSalary,
    Employer,
    SalaryCertificate,
    SalaryDeclaration,
    decimal_amount,
)


class StructuredInputError(ValueError):
    pass


def declaration_from_json(path: Path | str) -> SalaryDeclaration:
    if str(path) == "-":
        import sys

        return declaration_from_dict(json.load(sys.stdin))

    with Path(path).open(encoding="utf-8") as fh:
        return declaration_from_dict(json.load(fh))


def declaration_from_dict(data: dict[str, Any]) -> SalaryDeclaration:
    employer = _employer(data.get("employer"))
    employee_salaries = _employee_salaries(data)
    accounting_period = int(data.get("accounting_period") or _first_certificate(employee_salaries).year)
    creation_datetime = _datetime_value(data.get("creation_datetime"), "creation_datetime") or datetime.now().replace(microsecond=0)

    return SalaryDeclaration(
        employer=employer,
        employee_salaries=tuple(employee_salaries),
        accounting_period=accounting_period,
        creation_datetime=creation_datetime,
        schema_version=str(data.get("schema_version", "0.0")),
        comments=data.get("comments"),
    )


def prompt_declaration(stdin: TextIO | None = None, stdout: TextIO | None = None) -> SalaryDeclaration:
    stdin = stdin or __import__("sys").stdin
    stdout = stdout or __import__("sys").stdout

    def ask(label: str, default: str | None = None, *, required: bool = True) -> str:
        suffix = f" [{default}]" if default not in (None, "") else ""
        while True:
            stdout.write(f"{label}{suffix}: ")
            stdout.flush()
            value = stdin.readline()
            if value == "":
                raise StructuredInputError("Interactive input ended unexpectedly")
            value = value.strip()
            if value:
                return value
            if default is not None:
                return default
            if not required:
                return ""
            stdout.write("Required.\n")

    stdout.write("Employer\n")
    employer_name = ask("  Name")
    employer_street = ask("  Street")
    employer_zip = ask("  ZIP code")
    employer_city = ask("  City")
    employer_phone = ask("  Phone", required=False)

    stdout.write("\nEmployee\n")
    first_name = ask("  First name")
    last_name = ask("  Last name")
    employee_street = ask("  Street")
    employee_zip = ask("  ZIP code")
    employee_city = ask("  City")
    social_security_number = ask("  AHV/SV number", "756.0000.0000.00")
    date_of_birth = ask("  Date of birth", required=False)

    stdout.write("\nSalary certificate\n")
    year = ask("  Year")
    period_from = ask("  Period from", f"{year}-01-01")
    period_until = ask("  Period until", f"{year}-12-31")
    income = ask("  Ziffer 1 income")
    gross_income = ask("  Ziffer 8 gross income", income)
    social_security_contributions = ask("  Ziffer 9 AHV/ALV/NBUV contributions", "0")
    net_income = ask("  Ziffer 11 net income")
    creation_datetime = ask("  Creation datetime", f"{year}-12-31T12:00:00")

    return declaration_from_dict(
        {
            "employer": {
                "name": employer_name,
                "address": {
                    "street": employer_street,
                    "zip_code": employer_zip,
                    "city": employer_city,
                },
                "phone": employer_phone or None,
            },
            "employee": {
                "first_name": first_name,
                "last_name": last_name,
                "address": {
                    "street": employee_street,
                    "zip_code": employee_zip,
                    "city": employee_city,
                },
                "social_security_number": social_security_number,
                "date_of_birth": date_of_birth or None,
            },
            "certificate": {
                "year": int(year),
                "period_from": period_from,
                "period_until": period_until,
                "income": income,
                "gross_income": gross_income,
                "social_security_contributions": social_security_contributions,
                "net_income": net_income,
            },
            "creation_datetime": creation_datetime,
        }
    )


def _employer(value: Any) -> Employer:
    data = _object(value, "employer")
    return Employer(
        name=_required_str(data, "name", "employer.name"),
        address=_address(_required(data, "address", "employer.address"), "employer.address"),
        phone=_optional_str(data, "phone"),
        contact_name=_optional_str(data, "contact_name") or _optional_str(data, "name"),
        contact_email=_optional_str(data, "contact_email"),
        address_position=_optional_str(data, "address_position") or "RIGHT",  # type: ignore[arg-type]
    )


def _employee_salaries(data: dict[str, Any]) -> list[EmployeeSalary]:
    if "employees" in data:
        employees = _list(data["employees"], "employees")
        return [_employee_salary(entry, f"employees[{index}]") for index, entry in enumerate(employees)]

    employee = _employee(_required(data, "employee", "employee"), "employee")
    certificate = _certificate(_required(data, "certificate", "certificate"), "certificate")
    return [EmployeeSalary(employee=employee, certificates=(certificate,))]


def _employee_salary(value: Any, label: str) -> EmployeeSalary:
    data = _object(value, label)
    employee_data = data.get("employee") or data.get("person") or data
    employee = _employee(employee_data, f"{label}.employee")
    certificates = data.get("certificates")
    if certificates is None and "certificate" in data:
        certificates = [data["certificate"]]
    cert_list = _list(certificates, f"{label}.certificates")
    return EmployeeSalary(
        employee=employee,
        certificates=tuple(_certificate(entry, f"{label}.certificates[{index}]") for index, entry in enumerate(cert_list)),
    )


def _employee(value: Any, label: str) -> Employee:
    data = _object(value, label)
    return Employee(
        first_name=_required_str(data, "first_name", f"{label}.first_name"),
        last_name=_required_str(data, "last_name", f"{label}.last_name"),
        address=_address(_required(data, "address", f"{label}.address"), f"{label}.address"),
        social_security_number=_required_str(data, "social_security_number", f"{label}.social_security_number"),
        date_of_birth=_date_value(data.get("date_of_birth"), f"{label}.date_of_birth"),
        language=_optional_str(data, "language") or "de-CH",
        employee_number=_optional_str(data, "employee_number"),
        residence_canton=_optional_str(data, "residence_canton"),
        workplace_canton=_optional_str(data, "workplace_canton"),
    )


def _certificate(value: Any, label: str) -> SalaryCertificate:
    data = _object(value, label)
    return SalaryCertificate(
        year=int(_required(data, "year", f"{label}.year")),
        period_from=_required_date(data, "period_from", f"{label}.period_from"),
        period_until=_required_date(data, "period_until", f"{label}.period_until"),
        income=decimal_amount(_required(data, "income", f"{label}.income")),
        gross_income=decimal_amount(_required(data, "gross_income", f"{label}.gross_income")),
        social_security_contributions=decimal_amount(
            _required(data, "social_security_contributions", f"{label}.social_security_contributions")
        ),
        net_income=decimal_amount(_required(data, "net_income", f"{label}.net_income")),
        certificate_type=_optional_str(data, "certificate_type") or "LOHNAUSWEIS",  # type: ignore[arg-type]
        free_transport=_optional_bool(data, "free_transport"),
        canteen_lunch_check=_optional_bool(data, "canteen_lunch_check"),
        bvg_regular_contribution=_optional_decimal(data, "bvg_regular_contribution"),
        bvg_purchase_contribution=_optional_decimal(data, "bvg_purchase_contribution"),
        deduction_at_source=_optional_decimal(data, "deduction_at_source"),
        remarks=_optional_str(data, "remarks"),
    )


def _address(value: Any, label: str) -> Address:
    data = _object(value, label)
    return Address(
        street=_required_str(data, "street", f"{label}.street"),
        zip_code=_required_str(data, "zip_code", f"{label}.zip_code"),
        city=_required_str(data, "city", f"{label}.city"),
        complementary_line=_optional_str(data, "complementary_line"),
        postbox=_optional_str(data, "postbox"),
        locality=_optional_str(data, "locality"),
        country=_optional_str(data, "country"),
    )


def _first_certificate(employee_salaries: list[EmployeeSalary]) -> SalaryCertificate:
    if not employee_salaries or not employee_salaries[0].certificates:
        raise StructuredInputError("At least one employee certificate is required")
    return employee_salaries[0].certificates[0]


def _required_date(data: dict[str, Any], key: str, label: str) -> date:
    return _date_value(_required(data, key, label), label) or _raise(f"{label} is required")


def _date_value(value: Any, label: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise StructuredInputError(f"{label} must be a date in YYYY-MM-DD or DD.MM.YYYY format")


def _datetime_value(value: Any, label: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise StructuredInputError(f"{label} must be an ISO datetime, e.g. 2025-12-31T12:00:00") from exc


def _optional_decimal(data: dict[str, Any], key: str):
    value = data.get(key)
    if value in (None, ""):
        return None
    return decimal_amount(value)


def _optional_bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key, False)
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    raise StructuredInputError(f"{key} must be a boolean")


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _required_str(data: dict[str, Any], key: str, label: str) -> str:
    value = _required(data, key, label)
    return str(value)


def _required(data: dict[str, Any], key: str, label: str) -> Any:
    if key not in data or data[key] in (None, ""):
        raise StructuredInputError(f"{label} is required")
    return data[key]


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StructuredInputError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise StructuredInputError(f"{label} must be a non-empty list")
    return value


def _raise(message: str):
    raise StructuredInputError(message)
