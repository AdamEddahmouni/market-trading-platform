"""Versioned form-family taxonomy. Form type is not a trade direction."""

from __future__ import annotations

from dataclasses import dataclass

TAXONOMY_VERSION = "sec_form_taxonomy/1.0.0"

EIGHT_K_ITEMS_V1: dict[str, str] = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet Arrangement",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or Completed Interim Review",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
    "5.04": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
    "5.05": "Amendments to the Registrant's Code of Ethics, or Waiver of a Provision of the Code of Ethics",
    "5.06": "Change in Shell Company Status",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}


@dataclass(frozen=True, slots=True)
class FormClassification:
    form_type: str
    family: str
    is_amendment: bool
    taxonomy_version: str = TAXONOMY_VERSION


def is_amendment_form(form_type: str) -> bool:
    return "/A" in str(form_type).upper()


def _base_form(form_type: str) -> str:
    return str(form_type).upper().replace("/A", "").strip()


def classify_form(form_type: str) -> FormClassification:
    raw = str(form_type).strip()
    base = _base_form(raw)
    family = "OTHER"
    if base in {"8-K", "6-K"}:
        family = "CORPORATE_EVENT"
    elif base in {"S-1", "S-3", "424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8", "EFFECT", "RW"}:
        family = "CAPITAL_STRUCTURE"
    elif base in {"3", "4", "5", "13D", "SC 13D", "13G", "SC 13G", "13F-HR", "13F", "144"}:
        family = "OWNERSHIP"
    elif base in {"10-K", "10-Q", "20-F", "40-F"}:
        family = "FUNDAMENTAL"
    elif base in {"NT 10-K", "NT 10-Q", "25", "15", "15-12G"}:
        family = "DISTRESS"
    elif base.startswith("SC TO") or base in {"DEFM14A", "PREM14A", "DEF 14A", "PRE 14A"}:
        family = "CORPORATE_ACTION"
    return FormClassification(
        form_type=raw,
        family=family,
        is_amendment=is_amendment_form(raw),
    )


def eight_k_item_labels(items_field: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for token in str(items_field).replace(";", ",").split(","):
        key = token.strip()
        if not key:
            continue
        labels[key] = EIGHT_K_ITEMS_V1.get(key, "UNMAPPED_8K_ITEM")
    return labels
