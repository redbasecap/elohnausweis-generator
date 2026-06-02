from __future__ import annotations

import re
import subprocess
from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from .model import (
    Address,
    Employee,
    EmployeeSalary,
    Employer,
    SalaryCertificate,
    SalaryDeclaration,
    decimal_amount,
)


class ParseError(ValueError):
    pass


DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
AMOUNT_RE = re.compile(r"(?<![\d.])[-]?\d{1,3}(?:'?\d{3})*(?:[,.]\d{2})?(?![\d.])")
POSTAL_LINE_RE = re.compile(r"^(?P<zip>\d{4,6})\s+(?P<city>.+?)\s*$")
SV_NUMBER_RE = re.compile(r"\b756[.,]\d{4}[.,]\d{4}[.,]\d{2}\b")


def parse_pdf(path: Path) -> SalaryDeclaration:
    layout_text = extract_pdf_text(path, mode="layout")
    raw_text = extract_pdf_text(path, mode="raw")
    return parse_pdf_text(layout_text, address_text=raw_text)


def extract_pdf_text(path: Path, *, mode: str = "layout") -> str:
    if mode not in {"layout", "raw"}:
        raise ValueError(f"Unsupported pdftotext mode: {mode}")
    mode_flag = "-layout" if mode == "layout" else "-raw"
    try:
        return subprocess.check_output(["pdftotext", mode_flag, str(path), "-"], text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("pdftotext is required to parse Lohnausweis PDFs") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pdftotext failed for {path}") from exc


def parse_pdf_text(text: str, *, address_text: str | None = None) -> SalaryDeclaration:
    normalized = _normalize_text(text)
    address_lines = _non_empty_lines(_normalize_text(address_text or text))

    employee_name, employee_address = _extract_employee_address(address_lines)
    employer_name, employer_address, employer_phone = _extract_employer_address(address_lines)
    first_name, last_name = _split_person_name(employee_name)

    year = _extract_year(normalized)
    period_from, period_until = _extract_period(normalized)
    social_security_number = _extract_social_security_number(normalized)
    birth_date = _extract_birth_date(normalized)
    issue_date = _extract_issue_date(normalized)

    employee = Employee(
        first_name=first_name,
        last_name=last_name,
        address=employee_address,
        social_security_number=social_security_number,
        date_of_birth=birth_date,
    )
    employer = Employer(
        name=employer_name,
        address=employer_address,
        phone=employer_phone,
        contact_name=employer_name,
    )
    certificate = SalaryCertificate(
        certificate_type=_extract_certificate_type(normalized),
        year=year,
        period_from=period_from,
        period_until=period_until,
        income=_extract_required_amount(normalized, r"\b1\.\s*Lohn\b", r"\b2\.\s*Gehaltsnebenleistungen\b", "income z1"),
        gross_income=_extract_required_amount(normalized, r"\b8\.\s*Bruttolohn\b", r"\b9\.\s*Beitr", "gross income z8"),
        social_security_contributions=_extract_required_amount(normalized, r"\b9\.\s*Beitr", r"\b10\.\s*Berufliche\b", "social contributions z9"),
        net_income=_extract_required_amount(normalized, r"\b11\.\s*Nettolohn\b", r"\b12\.\s*Quellensteuerabzug\b", "net income z11"),
    )

    creation_datetime = datetime.combine(issue_date or date(year, 12, 31), time(hour=12))
    declaration = SalaryDeclaration(
        employer=employer,
        employee_salaries=(EmployeeSalary(employee=employee, certificates=(certificate,)),),
        accounting_period=year,
        creation_datetime=creation_datetime,
    )
    return replace(declaration, salary_counters=_salary_counters(declaration))


def _normalize_text(text: str) -> str:
    return text.replace("\xa0", " ").replace("\u200b", "")


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_certificate_type(text: str) -> str:
    header = "\n".join(text.splitlines()[:20])
    if re.search(r"\bB\s+X\b", header):
        return "RENTENBESCHEINIGUNG"
    return "LOHNAUSWEIS"


def _extract_year(text: str) -> int:
    match = re.search(r"\bD\s+(\d{4})\b", text)
    if not match:
        raise ParseError("Could not extract salary certificate year (field D)")
    return int(match.group(1))


def _extract_period(text: str) -> tuple[date, date]:
    match = re.search(r"\bE\s+(\d{2}\.\d{2}\.\d{4})\s+(\d{2}\.\d{2}\.\d{4})", text)
    if not match:
        raise ParseError("Could not extract salary period (field E)")
    return _parse_date(match.group(1)), _parse_date(match.group(2))


def _extract_social_security_number(text: str) -> str:
    match = SV_NUMBER_RE.search(text)
    if not match:
        raise ParseError("Could not extract AHV/SV number (field C)")
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) != 13:
        raise ParseError(f"Unexpected AHV/SV number length: {match.group(0)}")
    return f"{digits[:3]}.{digits[3:7]}.{digits[7:11]}.{digits[11:]}"


def _extract_birth_date(text: str) -> date | None:
    sv_match = SV_NUMBER_RE.search(text)
    search_text = text[sv_match.end() : sv_match.end() + 120] if sv_match else text
    match = DATE_RE.search(search_text)
    return _parse_date(match.group(0)) if match else None


def _extract_issue_date(text: str) -> date | None:
    matches = list(DATE_RE.finditer(text))
    if not matches:
        return None
    return _parse_date(matches[-1].group(0))


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%d.%m.%Y").date()


def _extract_required_amount(text: str, start_pattern: str, end_pattern: str, label: str) -> Decimal:
    amount = _extract_amount(text, start_pattern, end_pattern)
    if amount is None:
        raise ParseError(f"Could not extract {label}")
    return amount


def _extract_amount(text: str, start_pattern: str, end_pattern: str) -> Decimal | None:
    start = re.search(start_pattern, text, re.IGNORECASE | re.DOTALL)
    if not start:
        return None
    end = re.search(end_pattern, text[start.end() :], re.IGNORECASE | re.DOTALL)
    block = text[start.end() : start.end() + end.start()] if end else text[start.end() :]
    candidates = [candidate for candidate in AMOUNT_RE.findall(block) if _looks_like_amount(candidate)]
    return decimal_amount(candidates[-1]) if candidates else None


def _looks_like_amount(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 2


def _extract_employee_address(lines: list[str]) -> tuple[str, Address]:
    postal_indices = _postal_indices(lines)
    if not postal_indices:
        raise ParseError("Could not find any postal address block")
    return _address_before_postal_line(lines, postal_indices[0])


def _extract_employer_address(lines: list[str]) -> tuple[str, Address, str | None]:
    postal_indices = _postal_indices(lines)
    if not postal_indices:
        raise ParseError("Could not find employer postal address block")
    index = postal_indices[-1]
    name, address = _address_before_postal_line(lines, index)
    phone = _phone_after_line(lines, index)
    return name, address, phone


def _postal_indices(lines: list[str]) -> list[int]:
    return [index for index, line in enumerate(lines) if POSTAL_LINE_RE.match(line)]


def _address_before_postal_line(lines: list[str], postal_index: int) -> tuple[str, Address]:
    if postal_index < 2:
        raise ParseError(f"Postal line has no name/street prefix: {lines[postal_index]}")
    postal_match = POSTAL_LINE_RE.match(lines[postal_index])
    assert postal_match is not None
    name = lines[postal_index - 2]
    street = lines[postal_index - 1]
    return (
        name,
        Address(
            street=street,
            zip_code=postal_match.group("zip"),
            city=postal_match.group("city"),
        ),
    )


def _phone_after_line(lines: list[str], start_index: int) -> str | None:
    for line in lines[start_index + 1 : start_index + 8]:
        cleaned = re.sub(r"\s+", "", line)
        if re.fullmatch(r"\+?\d[\d()/.-]{5,}", cleaned):
            return cleaned
    return None


def _split_person_name(name: str) -> tuple[str, str]:
    parts = name.split()
    if len(parts) < 2:
        raise ParseError(f"Could not split employee name: {name}")
    return " ".join(parts[:-1]), parts[-1]


def _salary_counters(declaration: SalaryDeclaration) -> dict[str, int]:
    tax_salary_count = sum(len(entry.certificates) for entry in declaration.employee_salaries)
    return {
        "NumberOf-AHV-AVS-Salary-Tags": 0,
        "NumberOf-UVG-LAA-Salary-Tags": 0,
        "NumberOf-UVGZ-LAAC-Salary-Tags": 0,
        "NumberOf-KTG-AMC-Salary-Tags": 0,
        "NumberOf-BVG-LPP-Salary-Tags": 0,
        "NumberOf-FAK-CAF-Salary-Tags": 0,
        "NumberOf-TaxAnnuity-Tags": 0,
        "NumberOf-TaxSalary-Tags": tax_salary_count,
    }
