# eLohnausweis Generator

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/redbasecap)

Small Python package for generating eLohnausweis SSK-compatible XML from a Swiss
salary certificate PDF.

The generated XML targets the `SalaryDeclarationElohnOnline.xsd` format used by
the official eLohnausweis SSK online application. The SSK application can then
open/import the XML and create the final Lohnausweis PDF with barcode.

Official references:

- eLohnausweis SSK online: https://www.elohnausweis-ssk.ch/
- eLohnausweis XML schema: https://www.elohnausweis-ssk.ch/de/assets/documents/SalaryDeclarationElohnOnline.xsd
- User manual: https://www.elohnausweis-ssk.ch/de/assets/documents/Benutzerhandbuch_eLA.pdf

## Usage

From this directory:

```bash
python -m elohnausweis_generator \
  --pdf "/path/to/Lohnausweis.pdf" \
  --out "../build/elohnausweis.xml" \
  --validate
```

Generate XML from structured JSON instead of parsing a PDF:

```bash
python -m elohnausweis_generator \
  --json-in "examples/salary_certificate.example.json" \
  --out "../build/elohnausweis.xml" \
  --validate
```

Use `--json-in -` to read the JSON object from stdin:

```bash
cat examples/salary_certificate.example.json | python -m elohnausweis_generator \
  --json-in - \
  --out "../build/elohnausweis.xml"
```

Prompt for the required fields in the terminal:

```bash
python -m elohnausweis_generator \
  --interactive \
  --out "../build/elohnausweis.xml"
```

To also render the official PDF through the eLohnausweis SSK web application:

```bash
python -m elohnausweis_generator \
  --pdf "/path/to/Lohnausweis.pdf" \
  --out "../build/elohnausweis.xml" \
  --period-from 2025-04-28 \
  --period-until 2025-07-31 \
  --validate \
  --ssk-pdf "../build/elohnausweis.pdf"
```

You can also render an already generated XML:

```bash
python -m elohnausweis_generator \
  --xml-in "../build/elohnausweis.xml" \
  --ssk-pdf "../build/elohnausweis.pdf"
```

The SSK PDF renderer uses the public SSK web app in a headless browser via
Playwright. Install Playwright separately when using this mode:

```bash
python -m pip install playwright
python -m playwright install chromium
```

The rendered PDF is the official SSK web app output. Its "Ort und Datum" date is
set by the SSK app at render time.

`--validate` downloads the official XSD to a temporary directory and validates
the result with `xmllint` when available. The validator applies a local
compatibility fix for the current SSK XSD, where one internal type reference is
missing its namespace prefix and one unused complex type is not accepted by
`xmllint`.

For local development without installing the package:

```bash
PYTHONPATH=src python -m elohnausweis_generator --help
PYTHONPATH=src python -m unittest discover -s tests
```

## Current scope

Input can come from:

- a text-readable Lohnausweis PDF
- a structured JSON object
- an interactive terminal prompt

The PDF parser currently supports one text-readable Lohnausweis per PDF and extracts:

- certificate type
- AHV/SV number and date of birth
- year and employment period
- employee name/address
- employer name/address/phone
- salary figures 1, 8, 9, and 11

The XML writer is intentionally broader than the first parser and exposes a data
model that can later be filled from CSV, JSON, payroll systems, or manual input.

## JSON shape

Minimal single-certificate input:

```json
{
  "accounting_period": 2025,
  "creation_datetime": "2025-12-31T12:00:00",
  "employer": {
    "name": "Example Company AG",
    "address": {
      "street": "Example Street 1",
      "zip_code": "8000",
      "city": "Zurich"
    },
    "phone": "0440000000"
  },
  "employee": {
    "first_name": "Max",
    "last_name": "Muster",
    "address": {
      "street": "Sample Road 2",
      "zip_code": "3000",
      "city": "Bern"
    },
    "social_security_number": "756.0000.0000.00",
    "date_of_birth": "1990-02-01"
  },
  "certificate": {
    "year": 2025,
    "period_from": "2025-01-01",
    "period_until": "2025-12-31",
    "income": "1000.00",
    "gross_income": "1000.00",
    "social_security_contributions": "100.00",
    "net_income": "900.00"
  }
}
```

For multiple employees, use `employees` with one or more `certificates` per
employee. See `examples/salary_certificate.example.json` for the field names.
