from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from elohnausweis_generator import declaration_from_dict, declaration_from_json, parse_pdf_text, prompt_declaration
from elohnausweis_generator.cli import _apply_period_overrides
from elohnausweis_generator.xml_writer import NS, build_xml_tree


SAMPLE_TEXT = """
A       X        Lohnausweis - Certificat de salaire - Salary certificate
                  Rentenbescheinigung - Attestation de rentes - Pension statement
C 756.0000,0000.00                                              01.02.1990
D    2025                                E 01.01.2025                         31.12.2025

                                                                                                          Max Muster
                                                                                                          Beispielstrasse 10
                                                                                                          8000 Zuerich

 1. Lohn          soweit nicht unter Ziffer 2-7 aufzufuehren                                                                 1000

 2. Gehaltsnebenleistungen

 8. Bruttolohn total / Rente - Salaire brut total / Rente - Gross salary total / Pension
                                                                                                                             1000

 9. Beitraege AHV-IV/IV/EO/ALV/NBUV
                                                                                                                              100

10. Berufliche Vorsorge

11. Nettolohn / Rente - Salaire net / Rente - Net salary / Pension
                                                                                                                              900

12. Quellensteuerabzug - Retenue de l'impot a la source - Withholding tax deduction

Ort und Datum - Lieu et date - Place and
Zuerich, 31.12.2025

Muster AG
Musterweg 2
8001 Zuerich
0441234567
"""


STRUCTURED_SAMPLE = {
    "accounting_period": 2025,
    "creation_datetime": "2025-12-31T12:00:00",
    "employer": {
        "name": "Example Company AG",
        "address": {"street": "Example Street 1", "zip_code": "8000", "city": "Zurich"},
        "phone": "0440000000",
    },
    "employee": {
        "first_name": "Max",
        "last_name": "Muster",
        "address": {"street": "Sample Road 2", "zip_code": "3000", "city": "Bern"},
        "social_security_number": "756.0000.0000.00",
        "date_of_birth": "1990-02-01",
    },
    "certificate": {
        "year": 2025,
        "period_from": "2025-01-01",
        "period_until": "2025-12-31",
        "income": "1000.00",
        "gross_income": "1000.00",
        "social_security_contributions": "100.00",
        "net_income": "900.00",
        "free_transport": "false",
    },
}


class ElohnausweisGeneratorTest(unittest.TestCase):
    def test_parse_pdf_text_extracts_core_fields(self) -> None:
        declaration = parse_pdf_text(SAMPLE_TEXT)

        self.assertEqual(declaration.accounting_period, 2025)
        self.assertEqual(declaration.employer.name, "Muster AG")
        self.assertEqual(declaration.employer.phone, "0441234567")

        entry = declaration.employee_salaries[0]
        self.assertEqual(entry.employee.first_name, "Max")
        self.assertEqual(entry.employee.last_name, "Muster")
        self.assertEqual(entry.employee.social_security_number, "756.0000.0000.00")
        self.assertEqual(entry.employee.date_of_birth, date(1990, 2, 1))

        certificate = entry.certificates[0]
        self.assertEqual(certificate.period_from, date(2025, 1, 1))
        self.assertEqual(certificate.period_until, date(2025, 12, 31))
        self.assertEqual(str(certificate.income), "1000.00")
        self.assertEqual(str(certificate.social_security_contributions), "100.00")
        self.assertEqual(str(certificate.net_income), "900.00")

    def test_xml_writer_uses_ssk_namespace_and_counters(self) -> None:
        declaration = parse_pdf_text(SAMPLE_TEXT)
        root = build_xml_tree(declaration).getroot()

        self.assertEqual(root.tag, f"{{{NS}}}SalaryDeclaration")
        self.assertEqual(root.attrib["schemaVersion"], "0.0")

        ns = {"ela": NS}
        tax_salary_count = root.find(".//ela:NumberOf-TaxSalary-Tags", ns)
        self.assertIsNotNone(tax_salary_count)
        self.assertEqual(tax_salary_count.text, "1")

        sv_number = root.find(".//ela:SV-AS-Number", ns)
        self.assertIsNotNone(sv_number)
        self.assertEqual(sv_number.text, "756.0000.0000.00")

    def test_period_override_updates_certificate_dates(self) -> None:
        declaration = parse_pdf_text(SAMPLE_TEXT)

        updated = _apply_period_overrides(
            declaration,
            period_from=date(2025, 4, 28),
            period_until=date(2025, 7, 31),
        )

        certificate = updated.employee_salaries[0].certificates[0]
        self.assertEqual(certificate.period_from, date(2025, 4, 28))
        self.assertEqual(certificate.period_until, date(2025, 7, 31))

    def test_declaration_from_structured_dict(self) -> None:
        declaration = declaration_from_dict(STRUCTURED_SAMPLE)

        self.assertEqual(declaration.employer.name, "Example Company AG")
        self.assertEqual(declaration.employee_salaries[0].employee.address.city, "Bern")
        self.assertEqual(str(declaration.employee_salaries[0].certificates[0].net_income), "900.00")
        self.assertFalse(declaration.employee_salaries[0].certificates[0].free_transport)

    def test_declaration_from_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "input.json"
            path.write_text(json.dumps(STRUCTURED_SAMPLE), encoding="utf-8")

            declaration = declaration_from_json(path)

        self.assertEqual(declaration.accounting_period, 2025)
        self.assertEqual(declaration.employee_salaries[0].certificates[0].period_until, date(2025, 12, 31))

    def test_prompt_declaration_builds_structured_input(self) -> None:
        answers = "\n".join(
            [
                "Example Company AG",
                "Example Street 1",
                "8000",
                "Zurich",
                "0440000000",
                "Max",
                "Muster",
                "Sample Road 2",
                "3000",
                "Bern",
                "756.0000.0000.00",
                "1990-02-01",
                "2025",
                "2025-01-01",
                "2025-12-31",
                "1000.00",
                "1000.00",
                "100.00",
                "900.00",
                "2025-12-31T12:00:00",
            ]
        )

        declaration = prompt_declaration(stdin=io.StringIO(answers + "\n"), stdout=io.StringIO())

        self.assertEqual(declaration.employer.name, "Example Company AG")
        self.assertEqual(declaration.employee_salaries[0].employee.first_name, "Max")
        self.assertEqual(str(declaration.employee_salaries[0].certificates[0].gross_income), "1000.00")


if __name__ == "__main__":
    unittest.main()
