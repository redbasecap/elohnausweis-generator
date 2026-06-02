from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal


AddressPosition = Literal["LEFT", "RIGHT"]
CertificateType = Literal["LOHNAUSWEIS", "RENTENBESCHEINIGUNG"]


@dataclass(frozen=True)
class Address:
    street: str
    zip_code: str
    city: str
    complementary_line: str | None = None
    postbox: str | None = None
    locality: str | None = None
    country: str | None = None


@dataclass(frozen=True)
class Employer:
    name: str
    address: Address
    phone: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    address_position: AddressPosition = "RIGHT"


@dataclass(frozen=True)
class Employee:
    first_name: str
    last_name: str
    address: Address
    social_security_number: str
    date_of_birth: date | None = None
    language: str = "de-CH"
    employee_number: str | None = None
    residence_canton: str | None = None
    workplace_canton: str | None = None


@dataclass(frozen=True)
class SalaryCertificate:
    year: int
    period_from: date
    period_until: date
    income: Decimal
    gross_income: Decimal
    social_security_contributions: Decimal
    net_income: Decimal
    certificate_type: CertificateType = "LOHNAUSWEIS"
    free_transport: bool = False
    canteen_lunch_check: bool = False
    bvg_regular_contribution: Decimal | None = None
    bvg_purchase_contribution: Decimal | None = None
    deduction_at_source: Decimal | None = None
    remarks: str | None = None


@dataclass(frozen=True)
class EmployeeSalary:
    employee: Employee
    certificates: tuple[SalaryCertificate, ...]


@dataclass(frozen=True)
class SalaryDeclaration:
    employer: Employer
    employee_salaries: tuple[EmployeeSalary, ...]
    accounting_period: int
    creation_datetime: datetime
    schema_version: str = "0.0"
    comments: str | None = None
    salary_counters: dict[str, int] = field(default_factory=dict)


def decimal_amount(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    else:
        text = str(value).strip().replace("'", "")
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        amount = Decimal(text)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_amount(value: Decimal | int | str) -> str:
    return format(decimal_amount(value), "f")
