from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .model import Address, Employee, Employer, SalaryCertificate, SalaryDeclaration, format_amount


NS = "https://www.elohnausweis-ssk.ch/de/assets/documents/SalaryDeclarationElohnOnline.xsd"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", NS)
ET.register_namespace("xsi", XSI)


def build_xml_tree(declaration: SalaryDeclaration) -> ET.ElementTree:
    root = ET.Element(
        _tag("SalaryDeclaration"),
        {
            "schemaVersion": declaration.schema_version,
            f"{{{XSI}}}schemaLocation": f"{NS} {NS}",
        },
    )
    _append_company(root, declaration)
    _append_general_description(root, declaration)
    return ET.ElementTree(root)


def write_xml(declaration: SalaryDeclaration, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = build_xml_tree(declaration)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def _tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def _sub(parent: ET.Element, name: str, text: str | None = None, attrs: dict[str, str] | None = None) -> ET.Element:
    element = ET.SubElement(parent, _tag(name), attrs or {})
    if text is not None:
        element.text = text
    return element


def _append_company(root: ET.Element, declaration: SalaryDeclaration) -> None:
    company = _sub(root, "Company")
    _append_company_description(company, declaration.employer)

    staff = _sub(company, "Staff")
    for employee_salary in declaration.employee_salaries:
        person = _sub(staff, "Person")
        _append_particulars(person, employee_salary.employee)
        _append_work(person, employee_salary.employee)
        tax_salaries = _sub(person, "TaxSalaries")
        for certificate in employee_salary.certificates:
            _append_tax_salary(tax_salaries, certificate)

    counters = _sub(company, "SalaryCounters")
    counter_values = declaration.salary_counters or _default_counters(declaration)
    for name in (
        "NumberOf-AHV-AVS-Salary-Tags",
        "NumberOf-UVG-LAA-Salary-Tags",
        "NumberOf-UVGZ-LAAC-Salary-Tags",
        "NumberOf-KTG-AMC-Salary-Tags",
        "NumberOf-BVG-LPP-Salary-Tags",
        "NumberOf-FAK-CAF-Salary-Tags",
        "NumberOf-TaxAnnuity-Tags",
        "NumberOf-TaxSalary-Tags",
    ):
        _sub(counters, name, str(counter_values.get(name, 0)))


def _append_company_description(parent: ET.Element, employer: Employer) -> None:
    description = _sub(parent, "CompanyDescription")
    _sub(description, "AddressPosition", employer.address_position)
    name = _sub(description, "Name")
    _sub(name, "HR-RC-Name", employer.name)
    _append_address(description, employer.address)
    _sub(description, "BUR-REE")
    if employer.phone:
        _sub(description, "PhoneNumber", employer.phone)


def _append_particulars(parent: ET.Element, employee: Employee) -> None:
    particulars = _sub(parent, "Particulars")
    _sub(particulars, "Language", employee.language)
    social = _sub(particulars, "Social-InsuranceIdentification")
    _sub(social, "SV-AS-Number", employee.social_security_number)
    if employee.employee_number:
        _sub(particulars, "EmployeeNumber", employee.employee_number)
    _sub(particulars, "Lastname", employee.last_name)
    _sub(particulars, "Firstname", employee.first_name)
    if employee.date_of_birth:
        _sub(particulars, "DateOfBirth", employee.date_of_birth.isoformat())
    _append_address(particulars, employee.address)
    if employee.residence_canton:
        _sub(particulars, "ResidenceCanton", employee.residence_canton)


def _append_work(parent: ET.Element, employee: Employee) -> None:
    work = _sub(parent, "Work")
    if employee.workplace_canton:
        _sub(work, "WorkplaceCanton", employee.workplace_canton)


def _append_tax_salary(parent: ET.Element, certificate: SalaryCertificate) -> None:
    salary = _sub(parent, "TaxSalary")
    _sub(salary, "LohnausweisTyp", certificate.certificate_type)
    period = _sub(salary, "Period")
    _sub(period, "from", certificate.period_from.isoformat())
    _sub(period, "until", certificate.period_until.isoformat())
    _sub(salary, "Year", str(certificate.year))
    if certificate.free_transport:
        _sub(salary, "FreeTransport", "True")
    if certificate.canteen_lunch_check:
        _sub(salary, "CanteenLunchCheck", "True")
    _sub(salary, "Income", format_amount(certificate.income))
    _sub(salary, "GrossIncome", format_amount(certificate.gross_income))
    _sub(
        salary,
        "AHV-ALV-NBUV-AVS-AC-AANP-Contribution",
        format_amount(certificate.social_security_contributions),
    )
    if certificate.bvg_regular_contribution is not None or certificate.bvg_purchase_contribution is not None:
        bvg = _sub(salary, "BVG-LPP-Contribution")
        if certificate.bvg_regular_contribution is not None:
            _sub(bvg, "Regular", format_amount(certificate.bvg_regular_contribution))
        if certificate.bvg_purchase_contribution is not None:
            _sub(bvg, "Purchase", format_amount(certificate.bvg_purchase_contribution))
    _sub(salary, "NetIncome", format_amount(certificate.net_income))
    if certificate.deduction_at_source is not None:
        _sub(salary, "DeductionAtSource", format_amount(certificate.deduction_at_source))
    if certificate.remarks:
        _sub(salary, "Remark", certificate.remarks)


def _append_address(parent: ET.Element, address: Address) -> None:
    element = _sub(parent, "Address")
    if address.complementary_line:
        _sub(element, "ComplementaryLine", address.complementary_line)
    if address.street:
        _sub(element, "Street", address.street)
    if address.postbox:
        _sub(element, "Postbox", address.postbox)
    if address.locality:
        _sub(element, "Locality", address.locality)
    _sub(element, "ZIP-Code", address.zip_code)
    _sub(element, "City", address.city)
    if address.country:
        _sub(element, "Country", address.country)


def _append_general_description(root: ET.Element, declaration: SalaryDeclaration) -> None:
    general = _sub(root, "GeneralSalaryDeclarationDescription")
    _sub(general, "CreationDate", declaration.creation_datetime.isoformat())
    _sub(general, "AccountingPeriod", str(declaration.accounting_period))
    if declaration.employer.contact_name or declaration.employer.phone:
        contact = _sub(general, "ContactPerson")
        _sub(contact, "Name", declaration.employer.contact_name or declaration.employer.name)
        if declaration.employer.contact_email:
            _sub(contact, "EmailAddress", declaration.employer.contact_email)
        _sub(contact, "PhoneNumber", declaration.employer.phone or "unknown")
    if declaration.comments:
        _sub(general, "Comments", declaration.comments)


def _default_counters(declaration: SalaryDeclaration) -> dict[str, int]:
    tax_salary_count = sum(len(entry.certificates) for entry in declaration.employee_salaries)
    return {"NumberOf-TaxSalary-Tags": tax_salary_count}
