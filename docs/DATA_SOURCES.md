# DATA SOURCES: Official FMCSA & Federal Open Data Registry

**Last Catalog Verification**: October 22, 2026  
**Catalog Provider**: [data.transportation.gov](https://data.transportation.gov) (SODA Socrata Open Data API)  
**Authentication**: Cooperative Rate Limiting (5 req/sec unauthenticated, optional `SOCRATA_APP_TOKEN` via environment)

---

## 1. Official FMCSA Federal Datasets

| Dataset ID | Official Dataset Name | SODA Resource Endpoint | Purpose & Role | Contact Fields Present | Authority / Safety Fields |
|---|---|---|---|---|---|
| `az4n-8mr2` | **Company Census File** | `https://data.transportation.gov/resource/az4n-8mr2.json` | **Primary Carrier Discovery & Census Mirror** (MCMIS records for all active/pending carriers). | `PHONE`, `CELL_PHONE`, `EMAIL_ADDRESS`, `COMPANY_OFFICER_1`, `COMPANY_OFFICER_2`, `PHY_STREET`, `PHY_CITY`, `PHY_STATE`, `PHY_ZIP`, `CARRIER_MAILING_CITY`, `CARRIER_MAILING_STATE` | `STATUS_CODE` (`A`=Active), `CLASSDEF` (`AUTHORIZED FOR HIRE`), `DOCKET1` (MC#), `DOCKET1_STATUS_CODE`, `POWER_UNITS`, `FLEETSIZE`, `TOTAL_DRIVERS`, `CARRIER_OPERATION`, `SAFETY_RATING` |
| `kjg3-diqy` | **SMS Input - Motor Carrier Census Information** | `https://data.transportation.gov/resource/kjg3-diqy.json` | **Secondary Safety Measurement System (SMS) Census Validation** | `TELEPHONE`, `EMAIL_ADDRESS`, `LEGAL_NAME`, `DBA_NAME`, `PHY_STREET`, `PHY_CITY`, `PHY_STATE`, `PHY_ZIP` | `DOT_NUMBER`, `CARRIER_OPERATION`, `HM_FLAG`, `PC_FLAG`, `TOTAL_DRIVERS`, `POWER_UNITS` |
| `wb4f-neki` | **Motus RevokeSuspend - All With History** | `https://data.transportation.gov/resource/wb4f-neki.json` | **Authority History & Reinstatement Audit** (Historical tracking of revocation & suspension orders). | *None (Entity ID only)* | `DOCKET_NUMBER`, `USDOT_NUMBER`, `OP_AUTH_TYPE`, `ORDER1_SERVE_DATE`, `ORDER1_TYPE_DESC`, `ORDER1_EFFECTIVE_DATE` |
| `e67p-xyd5` | **Motus RevokeSuspend (Active Revocations)** | `https://data.transportation.gov/resource/e67p-xyd5.json` | **Real-Time Revocation Screening** (Hard suppression filter for revoked operating authorities). | *None (Entity ID only)* | `DOCKET_NUMBER`, `USDOT_NUMBER`, `OP_AUTH_TYPE`, `ORDER1_SERVE_DATE`, `ORDER1_TYPE_DESC` |
| `p2mt-9ige` | **OUT OF SERVICE ORDERS** | `https://data.transportation.gov/resource/p2mt-9ige.json` | **Federal Safety Out-of-Service Screening** (Disqualifies carriers under active federal OOS orders). | *None (Entity ID only)* | `DOT_NUMBER`, `LEGAL_NAME`, `DBA_NAME`, `OOS_DATE`, `OOS_REASON`, `STATUS`, `RESCIND_DATE` |

---

## 2. Field Analysis & Data Reality

1. **Phone Numbers (`PHONE`)**:
   - `az4n-8mr2` contains official business contact telephone numbers filed under Form MCS-150.
   - **Coverage in Target Small Fleet Segment**: **> 70% overall, 100% on registered active carriers**.
   - Treated as **unverified raw input** until normalized through `Normalizer.is_valid_phone_nanp()` and screened against DNC / suppression lists.

2. **Email Addresses (`EMAIL_ADDRESS`)**:
   - While the `EMAIL_ADDRESS` column exists in `az4n-8mr2` and `kjg3-diqy`, federal public disclosure redaction and MCS-150 filing patterns result in low direct email availability for small owner-operators.
   - Genuine decision-maker emails require **Workstream 3: The 4-Tier Waterfall Enrichment** (Hunter / Anymail / Apollo / Snov.io).

3. **Executive Decision Makers (`COMPANY_OFFICER_1`, `COMPANY_OFFICER_2`)**:
   - Registered officers (Owners, Partners, Presidents) are provided in `az4n-8mr2`.
   - When extracted, they are mapped to `Contact` entities with `is_decision_maker=True` subject to verification.

4. **Operating Authority & Safety (`STATUS_CODE`, `CLASSDEF`, `e67p-xyd5`)**:
   - `az4n-8mr2.status_code == 'A'` and `classdef == 'AUTHORIZED FOR HIRE'` confirms active interstate for-hire authority.
   - Cross-referenced against `e67p-xyd5` (active revocations) and `p2mt-9ige` (out-of-service orders) before issuing a `VERIFIED` authority score (+2.0).

---

## 3. Local Sync & Incremental Updates

- **Local Mirror Table**: `fmcsa_carrier_census` in `trucklead.db`.
- **Sync Protocol**:
  - Incremental via SHA-256 checksum (`raw_checksum` computed across record fields).
  - Rate-limited to max 5 requests/sec with exponential backoff on HTTP 429.
  - Socrata App Token supported via `SOCRATA_APP_TOKEN` in `.env`.
  - Resumable: queries local table first; only fetches missing state/fleet blocks from SODA.
- **Circuit Breaker & Fallback**:
  - `usdotlookup.com` scraping demoted to secondary fallback guarded by `ENABLE_USDOTLOOKUP_FALLBACK=False` and a 3-state circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN`).
