"""Generate eLohnausweis SSK-compatible XML."""

from .model import Address, Employee, Employer, SalaryCertificate, SalaryDeclaration
from .pdf_parser import parse_pdf, parse_pdf_text
from .structured_input import declaration_from_dict, declaration_from_json, prompt_declaration
from .xml_writer import build_xml_tree, write_xml

__all__ = [
    "Address",
    "Employee",
    "Employer",
    "SalaryCertificate",
    "SalaryDeclaration",
    "build_xml_tree",
    "declaration_from_dict",
    "declaration_from_json",
    "parse_pdf",
    "parse_pdf_text",
    "prompt_declaration",
    "write_xml",
]
