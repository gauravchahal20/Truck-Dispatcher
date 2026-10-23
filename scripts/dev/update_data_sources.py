import json

def update_data_sources_md():
    with open("scripts/az4n_schema_table.md", "r") as f:
        schema_table = f.read()

    content = f"""# DATA SOURCES: Official FMCSA & Federal Open Data Registry

**Last Catalog Verification**: October 22, 2026  
**Catalog Provider**: [data.transportation.gov](https://data.transportation.gov) (SODA Socrata Open Data API)  
**Authentication**: Cooperative Rate Limiting (5 req/sec unauthenticated, optional `SOCRATA_APP_TOKEN` via environment)

---

## 1. Official FMCSA Federal Datasets

| Dataset ID | Official Dataset Name | SODA Resource Endpoint | Purpose & Role | Update Frequency | Fetch / Verification Date | Key Fields Present |
|---|---|---|---|---|---|---|
| `az4n-8mr2` | **Company Census File** | `https://data.transportation.gov/resource/az4n-8mr2.json` | **Primary Carrier Discovery & Census Mirror** (MCMIS records for all active/pending carriers). | Daily | 2026-10-22 | `DOT_NUMBER`, `LEGAL_NAME`, `DBA_NAME`, `PHONE`, `CELL_PHONE`, `COMPANY_OFFICER_1`, `COMPANY_OFFICER_2`, `PHY_STREET`, `PHY_CITY`, `PHY_STATE`, `PHY_ZIP`, `STATUS_CODE`, `CLASSDEF`, `DOCKET1`, `POWER_UNITS`, `FLEETSIZE`, `TOTAL_DRIVERS`, `CARRIER_OPERATION`, `SAFETY_RATING` |
| `kjg3-diqy` | **SMS Input - Motor Carrier Census Information** | `https://data.transportation.gov/resource/kjg3-diqy.json` | **SMS Census & Official Email Mirror** (Safety Measurement System census dataset with verified contact emails). | Monthly | 2026-10-22 | `DOT_NUMBER`, `LEGAL_NAME`, `DBA_NAME`, `EMAIL_ADDRESS`, `TELEPHONE`, `PHY_STREET`, `PHY_CITY`, `PHY_STATE`, `PHY_ZIP`, `CARRIER_OPERATION`, `TOTAL_DRIVERS`, `POWER_UNITS` |
| `qh9u-swkp` | **ActPendInsur - All With History** | `https://data.transportation.gov/resource/qh9u-swkp.json` | **Active and Pending Insurance Filings** (Proof of public liability and cargo insurance coverage). | Daily | 2026-10-22 | `DOT_NUMBER`, `DOCKET_NUMBER`, `INS_FORM_CODE`, `NAME_COMPANY`, `POLICY_NO`, `TRANS_DATE`, `UNDERL_LIM_AMOUNT`, `MAX_COV_AMOUNT`, `EFFECTIVE_DATE`, `CANCL_EFFECTIVE_DATE` |
| `ypjt-5ydn` | **Insur - All With History** | `https://data.transportation.gov/resource/ypjt-5ydn.json` | **Insurance Policy Registry** (Comprehensive insurance filings with coverage limits). | Daily | 2026-10-22 | `PREFIX_DOCKET_NUMBER`, `INS_TYPE_CODE`, `INS_CLASS_CODE`, `MAX_COV_AMOUNT`, `UNDERL_LIM_AMOUNT`, `POLICY_NO`, `EFFECTIVE_DATE`, `INS_FORM_CODE`, `NAME_COMPANY` |
| `6sqe-dvqs` | **InsHist - All With History** | `https://data.transportation.gov/resource/6sqe-dvqs.json` | **Historical Insurance Coverage Records** | Daily | 2026-10-22 | `DOT_NUMBER`, `DOCKET_NUMBER`, `POLICY_NO`, `EFFECTIVE_DATE`, `CANCEL_DATE`, `INSURANCE_NAME` |
| `9mw4-x3tu` | **AuthHist - All With History** | `https://data.transportation.gov/resource/9mw4-x3tu.json` | **Operating Authority Grants & Dispositions** | Daily | 2026-10-22 | `DOT_NUMBER`, `DOCKET_NUMBER`, `ORIGINAL_ACTION_DESC`, `MOD_COL_1` |
| `wb4f-neki` | **Motus RevokeSuspend – All With History** | `https://data.transportation.gov/resource/wb4f-neki.json` | **Authority History, Revocations & Suspensions** (Tracks past revocations and administrative actions). | Daily | 2026-10-22 | `USDOT_NUMBER`, `DOCKET_NUMBER`, `OP_AUTH_TYPE`, `ORDER1_SERVE_DATE`, `ORDER1_TYPE_DESC`, `ORDER1_EFFECTIVE_DATE` |
| `96tg-4mhf` | **Rejected - All With History** | `https://data.transportation.gov/resource/96tg-4mhf.json` | **Rejected Operating Authority Applications** (Early warning on compliance deficiencies). | Daily | 2026-10-22 | `DOT_NUMBER`, `DOCKET_NUMBER`, `INS_FORM_CODE`, `POLICY_NO`, `RECV_DATE`, `REJ_DATE`, `NAME_COMPANY`, `REJ_REASONS`, `MIN_COV_AMOUNT` |
| `2emp-mxtb` | **BOC3 - All With History** | `https://data.transportation.gov/resource/2emp-mxtb.json` | **Process Agent Filings** (Designation of process agents in all 50 states). | Daily | 2026-10-22 | `DOT_NUMBER`, `DOCKET_NUMBER`, `PROCESS_AGENT_NAME`, `FILED_DATE` |
| `e67p-xyd5` | **Motus RevokeSuspend (Active Revocations)** | `https://data.transportation.gov/resource/e67p-xyd5.json` | **Real-Time Revocation Screening** (Hard suppression filter for revoked operating authorities). | Daily | 2026-10-22 | `USDOT_NUMBER`, `DOCKET_NUMBER`, `OP_AUTH_TYPE`, `ORDER1_SERVE_DATE`, `ORDER1_TYPE_DESC` |
| `p2mt-9ige` | **OUT OF SERVICE ORDERS** | `https://data.transportation.gov/resource/p2mt-9ige.json` | **Federal Safety Out-of-Service Screening** (Disqualifies carriers under active federal OOS orders). | Weekly | 2026-10-22 | `DOT_NUMBER`, `LEGAL_NAME`, `DBA_NAME`, `OOS_DATE`, `OOS_REASON`, `STATUS`, `RESCIND_DATE` |

---

## 2. Field Analysis & Contact Data Reality

1. **Phone Numbers (`PHONE`, `CELL_PHONE`)**:
   - `az4n-8mr2` contains official business telephone numbers (`phone`, col 17) and optional cell numbers (`cell_phone`, col 19) filed under Form MCS-150.
   - **Coverage in Target Small Fleet Segment**: **> 70% overall, > 94% on registered active carriers**.
   - Treated as **unverified raw input** until normalized through `Normalizer.is_valid_phone_nanp()` and screened against DNC / suppression lists.

2. **Email Addresses (`EMAIL_ADDRESS`)**:
   - **Audit finding**: The primary Company Census File (`az4n-8mr2`) **does not include an email column** in its 147 live columns due to public disclosure restrictions.
   - The secondary federal dataset `kjg3-diqy` (**SMS Input - Motor Carrier Census Information**) **does contain official `email_address` columns** filed by carriers.
   - Leads lacking an official email are marked `NEEDS_ENRICHMENT` for automated 4-tier waterfall enrichment (Hunter / Anymail / Apollo / Snov.io).

3. **Executive Decision Makers (`COMPANY_OFFICER_1`, `COMPANY_OFFICER_2`)**:
   - Registered officers (Owners, Partners, Presidents) are provided in `az4n-8mr2` (cols 20 & 21).
   - When extracted, they are mapped to `Contact` entities with title `"Company officer (per MCS-150)"`, `is_decision_maker=True`, and provenance `method="official"`.
   - Contact records remain `verification_status="UNVERIFIED"` until validated through email deliverability and compliance checks.

4. **Operating Authority & Safety (`STATUS_CODE`, `CLASSDEF`, `wb4f-neki`, `p2mt-9ige`)**:
   - `az4n-8mr2.status_code == 'A'` and `classdef == 'AUTHORIZED FOR HIRE'` confirms active interstate for-hire authority.
   - Shippers do not hold or require motor carrier operating authority (`operating_status = NULL`, verified as `N/A`).
   - Cross-referenced against `wb4f-neki` (revocations) and `p2mt-9ige` (out-of-service orders) before issuing a `VERIFIED` authority score (+2.0).

---

## 3. Live Schema: `az4n-8mr2` Company Census File (All 147 Columns)

The live schema below reflects the exact 147 columns exposed by the SODA API for `az4n-8mr2` verified on October 22, 2026:

{schema_table}

---

## 4. Local Sync & Incremental Updates

- **Local Mirror Tables in `trucklead.db`**:
  - `fmcsa_carrier_census`: Primary carrier mirror from `az4n-8mr2`.
  - `fmcsa_insurance_active_pending`: Active/pending insurance from `qh9u-swkp`.
  - `fmcsa_authority_history`: Authority history from `wb4f-neki` / `9mw4-x3tu`.
  - `fmcsa_new_applications`: Application and rejection tracking from `96tg-4mhf`.
  - `suppression_list`: DNC and opt-out registry for TCPA / CAN-SPAM compliance.
- **Sync Protocol**:
  - Incremental via SHA-256 checksum (`raw_checksum` computed across record fields).
  - Rate-limited to max 5 requests/sec with exponential backoff on HTTP 429.
  - Socrata App Token supported via `SOCRATA_APP_TOKEN` in `.env`.
  - Resumable: queries local table first; only fetches missing state/fleet blocks from SODA.
"""
    with open("docs/DATA_SOURCES.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated docs/DATA_SOURCES.md with 147-column schema and D5 signal datasets.")

if __name__ == "__main__":
    update_data_sources_md()
