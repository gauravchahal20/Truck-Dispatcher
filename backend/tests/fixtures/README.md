# Test Fixtures Provenance Registry (`backend/tests/fixtures/`)

This directory contains offline test fixtures used by the test suite to ensure 100% offline determinism, sub-second execution, and complete isolation from external network dependencies.

## Fixture Inventory & Classification

| Fixture File | Type | Source Origin | Retrieval / Creation Date | Scrubbing & Structure Preservation |
|---|---|---|---|---|
| `carrier_website.html` | **Synthetic (Recorded Template)** | Modeled after live carrier websites (`lonestareaglexpress.com`) | 2026-10-22 | Contains realistic corporate header, `#leadership` executive biographies, and `#contact` footer. All personal PII scrubbed to fictitious names (`Marcus Vance`) with valid NANP non-fictional phone formats. |
| `fmcsa_safer_snapshot.html` | **Recorded (Structure Preserved)** | `https://safer.fmcsa.dot.gov/query.asp` | 2026-10-22 | Exact table layout, HTML markup, and font tag conventions (`<font color="green"><b>AUTHORIZED FOR Property</b></font>`) matching SAFER company snapshot response. PII scrubbed. |
| `fmcsa_li_insurance.html` | **Recorded (Structure Preserved)** | `https://li-public.fmcsa.dot.gov/` | 2026-10-22 | Exact table headers (`table.report-table`), BIPD insurance thresholds ($750k required / $1M on file), and policy lines from L&I. PII scrubbed. |
| `usdotlookup_carrier_page.html` | **Recorded (Structure Preserved)** | `https://usdotlookup.com/` | 2026-10-22 | Exact DOM structure (`div.carrier-card`, `h3 a[href]`, strong tags) preserved from carrier directory listings. Validated against HTML parser. PII scrubbed. |

---

## Maintenance & Monthly Drift Verification

- **Offline Rule**: Default `pytest` execution **MUST NOT** fetch live web pages. All parser tests run against the fixtures above.
- **Monthly Live Drift Check**: Run `pytest -m live backend/tests/test_parser_drift.py` on a monthly schedule.
  - Compares current live web response schemas and DOM selector paths against the recorded fixtures.
  - Flags any breaking DOM structure or parser drift before it impacts production runs.
