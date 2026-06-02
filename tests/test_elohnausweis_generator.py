from __future__ import annotations

import unittest
from datetime import date

from elohnausweis_generator import parse_pdf_text
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


if __name__ == "__main__":
    unittest.main()
