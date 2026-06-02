from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from .model import SalaryDeclaration
from .pdf_parser import parse_pdf
from .ssk_renderer import render_pdf_with_ssk
from .xml_writer import write_xml


OFFICIAL_SCHEMA_URL = "https://www.elohnausweis-ssk.ch/de/assets/documents/SalaryDeclarationElohnOnline.xsd"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate eLohnausweis SSK-compatible XML.")
    parser.add_argument("--pdf", type=Path, help="Input Lohnausweis PDF.")
    parser.add_argument("--xml-in", type=Path, help="Existing eLohnausweis XML to validate or render.")
    parser.add_argument("--out", type=Path, help="Output XML path.")
    parser.add_argument("--validate", action="store_true", help="Validate XML against the eLohnausweis SSK XSD.")
    parser.add_argument("--schema", type=Path, help="Local SalaryDeclarationElohnOnline.xsd path.")
    parser.add_argument("--schema-url", default=OFFICIAL_SCHEMA_URL, help="Schema URL used when --validate has no --schema.")
    parser.add_argument("--ssk-pdf", type=Path, help="Render the XML to PDF through the eLohnausweis SSK web app.")
    parser.add_argument("--ssk-url", default="https://www.elohnausweis-ssk.ch/", help="eLohnausweis SSK web app URL.")
    parser.add_argument("--period-from", type=_parse_cli_date, help="Override salary period start date, e.g. 2025-04-28 or 28.04.2025.")
    parser.add_argument("--period-until", type=_parse_cli_date, help="Override salary period end date, e.g. 2025-07-31 or 31.07.2025.")
    args = parser.parse_args(argv)

    xml_path = _resolve_xml_path(args, parser)
    if args.xml_in and (args.period_from or args.period_until):
        parser.error("--period-from/--period-until can only be used while generating XML from --pdf.")

    if args.pdf:
        declaration = parse_pdf(args.pdf)
        declaration = _apply_period_overrides(
            declaration,
            period_from=args.period_from,
            period_until=args.period_until,
        )
        assert args.out is not None
        write_xml(declaration, args.out)
        print(f"Wrote {args.out}")

    if args.validate:
        schema_path = args.schema or _download_schema(args.schema_url)
        effective_schema_path = _validate_xml(xml_path, schema_path)
        print(f"Validated {xml_path} against {effective_schema_path}")

    if args.ssk_pdf:
        render_pdf_with_ssk(xml_path=xml_path, pdf_path=args.ssk_pdf, app_url=args.ssk_url)
        print(f"Rendered {args.ssk_pdf} through eLohnausweis SSK")

    return 0


def _resolve_xml_path(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Path:
    if args.pdf and args.xml_in:
        parser.error("Use either --pdf or --xml-in, not both.")
    if args.pdf:
        if not args.out:
            parser.error("--out is required with --pdf.")
        return args.out
    if args.xml_in:
        if args.out:
            parser.error("--out is only used when generating XML from --pdf.")
        return args.xml_in
    parser.error("Either --pdf or --xml-in is required.")
    raise AssertionError("unreachable")


def _parse_cli_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"Invalid date {value!r}; use YYYY-MM-DD or DD.MM.YYYY.")


def _apply_period_overrides(
    declaration: SalaryDeclaration,
    *,
    period_from: date | None = None,
    period_until: date | None = None,
) -> SalaryDeclaration:
    if period_from is None and period_until is None:
        return declaration

    employee_salaries = []
    for employee_salary in declaration.employee_salaries:
        certificates = tuple(
            replace(
                certificate,
                period_from=period_from or certificate.period_from,
                period_until=period_until or certificate.period_until,
            )
            for certificate in employee_salary.certificates
        )
        employee_salaries.append(replace(employee_salary, certificates=certificates))

    return replace(declaration, employee_salaries=tuple(employee_salaries))


def _download_schema(schema_url: str) -> Path:
    target = Path(tempfile.gettempdir()) / "SalaryDeclarationElohnOnline.xsd"
    urllib.request.urlretrieve(schema_url, target)
    return target


def _validate_xml(xml_path: Path, schema_path: Path) -> Path:
    schema_path = _schema_path_for_xmllint(schema_path)
    try:
        subprocess.run(["xmllint", "--noout", "--schema", str(schema_path), str(xml_path)], check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("xmllint is required for --validate") from exc
    return schema_path


def _schema_path_for_xmllint(schema_path: Path) -> Path:
    text = schema_path.read_text(encoding="utf-8")
    fixed = text.replace('type="AddressType"', 'type="tns:AddressType"')
    fixed = re.sub(
        r'\s*<xs:complexType name="StandardRemarkType">.*?(?=\s*<xs:complexType name="GrantType">)',
        """
    <xs:complexType name="StandardRemarkType">
        <xs:sequence>
            <xs:any minOccurs="0" maxOccurs="unbounded" processContents="skip"/>
        </xs:sequence>
    </xs:complexType>
""",
        fixed,
        flags=re.DOTALL,
    )
    if fixed == text:
        return schema_path

    patched = Path(tempfile.gettempdir()) / f"{schema_path.stem}.xmllint{schema_path.suffix}"
    patched.write_text(fixed, encoding="utf-8")
    return patched
