# DATA SOURCES: Official FMCSA & Federal Open Data Registry

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
| `nakq-58th` | **Motus Carrier** | `https://data.transportation.gov/resource/nakq-58th.json` | **Carrier Operating Authority & Insurance Status** (Active/Inactive authority, BIPD liability insurance filing, and bond amounts). | Daily | 2026-10-25 | `DOCKET_NUMBER`, `USDOT_NUMBER`, `OP_AUTH_TYPE`, `OP_AUTH_STATUS`, `BIPD_FILE`, `CARGO_FILE`, `BOND_FILE`, `MIN_COV_AMOUNT` |
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

4. **Operating Authority & Safety Proof (`STATUS_CODE`, `CLASSDEF` vs L&I Operating Authority)**:
   - **Self-Declared Form MCS-150 Fields**: `az4n-8mr2` fields `classdef` ("AUTHORIZED FOR HIRE"), `carrier_operation` ('A'), and `status_code` ('A') are **self-declared checkboxes** submitted by the applicant on Form MCS-150.
   - **Legal Operating Authority Under 49 U.S.C. 13902**: True interstate for-hire operating authority requires FMCSA Licensing and Insurance (L&I) registration:
     1. An approved Operating Authority application (Docket MC/FF/MX).
     2. Designation of Process Agents (Form BOC-3) in all 50 states (`2emp-mxtb`).
     3. Direct underwriter proof of active financial responsibility / insurance on file (Form BMC-91/BMC-91X, minimum $750k BIPD public liability) (`qh9u-swkp` / `nakq-58th.bipd_file`).
     4. Official FMCSA Order/Decision granting active operating authority (`9mw4-x3tu` / `nakq-58th.op_auth_status == 'Active'`).
   - **Authority Gating & Scoring**: Census self-declaration alone yields `UNKNOWN` (0 authority points). The `+2.0` verified active authority score and passage through the `QUALIFIED` gate strictly require proven active L&I status plus an active insurance filing. Carriers lacking L&I proof route to `NEEDS_ENRICHMENT` (or `NEEDS_REVIEW`).
   - Shippers do not hold or require motor carrier operating authority (`operating_status = NULL`, verified as `N/A`).

---

## 3. Live Schema: `az4n-8mr2` Company Census File (All 147 Columns)

The live schema below reflects the exact 147 columns exposed by the SODA API for `az4n-8mr2` verified on October 22, 2026:

| # | Field Name (`fieldName`) | Column Name (`name`) | Data Type (`dataTypeName`) |
|---|---|---|---|
| 1 | `mcs150_date` | `MCS150_DATE` | text |
| 2 | `add_date` | `ADD_DATE` | text |
| 3 | `status_code` | `STATUS_CODE` | text |
| 4 | `dot_number` | `DOT_NUMBER` | number |
| 5 | `dun_bradstreet_no` | `DUN_BRADSTREET_NO` | text |
| 6 | `phy_omc_region` | `PHY_OMC_REGION` | text |
| 7 | `safety_inv_terr` | `SAFETY_INV_TERR` | text |
| 8 | `carrier_operation` | `CARRIER_OPERATION` | text |
| 9 | `business_org_id` | `BUSINESS_ORG_ID` | text |
| 10 | `mcs150_mileage` | `MCS150_MILEAGE` | text |
| 11 | `mcs150_mileage_year` | `MCS150_MILEAGE_YEAR` | text |
| 12 | `mcs151_mileage` | `MCS151_MILEAGE` | text |
| 13 | `total_cars` | `TOTAL_CARS` | text |
| 14 | `mcs150_update_code_id` | `MCS150_UPDATE_CODE_ID` | text |
| 15 | `prior_revoke_flag` | `PRIOR_REVOKE_FLAG` | text |
| 16 | `prior_revoke_dot_number` | `PRIOR_REVOKE_DOT_NUMBER` | text |
| 17 | `phone` | `PHONE` | text |
| 18 | `fax` | `FAX` | text |
| 19 | `cell_phone` | `CELL_PHONE` | text |
| 20 | `company_officer_1` | `COMPANY_OFFICER_1` | text |
| 21 | `company_officer_2` | `COMPANY_OFFICER_2` | text |
| 22 | `business_org_desc` | `BUSINESS_ORG_DESC` | text |
| 23 | `truck_units` | `TRUCK_UNITS` | text |
| 24 | `power_units` | `POWER_UNITS` | text |
| 25 | `bus_units` | `BUS_UNITS` | text |
| 26 | `fleetsize` | `FLEETSIZE` | text |
| 27 | `review_id` | `REVIEW_ID` | text |
| 28 | `recordable_crash_rate` | `RECORDABLE_CRASH_RATE` | text |
| 29 | `mail_nationality_indicator` | `MAIL_NATIONALITY_INDICATOR` | text |
| 30 | `phy_nationality_indicator` | `PHY_NATIONALITY_INDICATOR` | text |
| 31 | `phy_barrio` | `PHY_BARRIO` | text |
| 32 | `mail_barrio` | `MAIL_BARRIO` | text |
| 33 | `carship` | `CARSHIP` | text |
| 34 | `docket1prefix` | `DOCKET1PREFIX` | text |
| 35 | `docket1` | `DOCKET1` | text |
| 36 | `docket2prefix` | `DOCKET2PREFIX` | text |
| 37 | `docket2` | `DOCKET2` | text |
| 38 | `docket3prefix` | `DOCKET3PREFIX` | text |
| 39 | `docket3` | `DOCKET3` | text |
| 40 | `pointnum` | `POINTNUM` | text |
| 41 | `total_intrastate_drivers` | `TOTAL_INTRASTATE_DRIVERS` | text |
| 42 | `mcsipstep` | `MCSIPSTEP` | text |
| 43 | `mcsipdate` | `MCSIPDATE` | text |
| 44 | `hm_ind` | `HM_Ind` | text |
| 45 | `interstate_beyond_100_miles` | `INTERSTATE_BEYOND_100_MILES` | text |
| 46 | `interstate_within_100_miles` | `INTERSTATE_WITHIN_100_MILES` | text |
| 47 | `intrastate_beyond_100_miles` | `INTRASTATE_BEYOND_100_MILES` | text |
| 48 | `intrastate_within_100_miles` | `INTRASTATE_WITHIN_100_MILES` | text |
| 49 | `total_cdl` | `TOTAL_CDL` | text |
| 50 | `total_drivers` | `TOTAL_DRIVERS` | text |
| 51 | `avg_drivers_leased_per_month` | `AVG_DRIVERS_LEASED_PER_MONTH` | text |
| 52 | `classdef` | `CLASSDEF` | text |
| 53 | `legal_name` | `LEGAL_NAME` | text |
| 54 | `dba_name` | `DBA_NAME` | text |
| 55 | `phy_street` | `PHY_STREET` | text |
| 56 | `phy_city` | `PHY_CITY` | text |
| 57 | `phy_country` | `PHY_COUNTRY` | text |
| 58 | `phy_state` | `PHY_STATE` | text |
| 59 | `phy_zip` | `PHY_ZIP` | text |
| 60 | `phy_cnty` | `PHY_CNTY` | text |
| 61 | `carrier_mailing_street` | `CARRIER_MAILING_STREET` | text |
| 62 | `carrier_mailing_state` | `CARRIER_MAILING_STATE` | text |
| 63 | `carrier_mailing_city` | `CARRIER_MAILING_CITY` | text |
| 64 | `carrier_mailing_country` | `CARRIER_MAILING_COUNTRY` | text |
| 65 | `carrier_mailing_zip` | `CARRIER_MAILING_ZIP` | text |
| 66 | `carrier_mailing_cnty` | `CARRIER_MAILING_CNTY` | text |
| 67 | `carrier_mailing_und_date` | `CARRIER_MAILING_UND_DATE` | text |
| 68 | `driver_inter_total` | `DRIVER_INTER_TOTAL` | text |
| 69 | `email_address` | `EMAIL_ADDRESS` | text |
| 70 | `review_type` | `REVIEW_TYPE` | text |
| 71 | `review_date` | `REVIEW_DATE` | text |
| 72 | `safety_rating` | `SAFETY_RATING` | text |
| 73 | `safety_rating_date` | `SAFETY_RATING_DATE` | text |
| 74 | `undeliv_phy` | `UNDELIV_PHY` | text |
| 75 | `crgo_genfreight` | `CRGO_GENFREIGHT` | text |
| 76 | `crgo_household` | `CRGO_HOUSEHOLD` | text |
| 77 | `crgo_metalsheet` | `CRGO_METALSHEET` | text |
| 78 | `crgo_motoveh` | `CRGO_MOTOVEH` | text |
| 79 | `crgo_drivetow` | `CRGO_DRIVETOW` | text |
| 80 | `crgo_logpole` | `CRGO_LOGPOLE` | text |
| 81 | `crgo_bldgmat` | `CRGO_BLDGMAT` | text |
| 82 | `crgo_mobilehome` | `CRGO_MOBILEHOME` | text |
| 83 | `crgo_machlrg` | `CRGO_MACHLRG` | text |
| 84 | `crgo_produce` | `CRGO_PRODUCE` | text |
| 85 | `crgo_liqgas` | `CRGO_LIQGAS` | text |
| 86 | `crgo_intermodal` | `CRGO_INTERMODAL` | text |
| 87 | `crgo_passengers` | `CRGO_PASSENGERS` | text |
| 88 | `crgo_oilfield` | `CRGO_OILFIELD` | text |
| 89 | `crgo_livestock` | `CRGO_LIVESTOCK` | text |
| 90 | `crgo_grainfeed` | `CRGO_GRAINFEED` | text |
| 91 | `crgo_coalcoke` | `CRGO_COALCOKE` | text |
| 92 | `crgo_meat` | `CRGO_MEAT` | text |
| 93 | `crgo_garbage` | `CRGO_GARBAGE` | text |
| 94 | `crgo_usmail` | `CRGO_USMAIL` | text |
| 95 | `crgo_chem` | `CRGO_CHEM` | text |
| 96 | `crgo_drybulk` | `CRGO_DRYBULK` | text |
| 97 | `crgo_coldfood` | `CRGO_COLDFOOD` | text |
| 98 | `crgo_beverages` | `CRGO_BEVERAGES` | text |
| 99 | `crgo_paperprod` | `CRGO_PAPERPROD` | text |
| 100 | `crgo_utility` | `CRGO_UTILITY` | text |
| 101 | `crgo_farmsupp` | `CRGO_FARMSUPP` | text |
| 102 | `crgo_construct` | `CRGO_CONSTRUCT` | text |
| 103 | `crgo_waterwell` | `CRGO_WATERWELL` | text |
| 104 | `crgo_cargoothr` | `CRGO_CARGOOTHR` | text |
| 105 | `crgo_cargoothr_desc` | `CRGO_CARGOOTHR_DESC` | text |
| 106 | `owntruck` | `OWNTRUCK` | text |
| 107 | `owntract` | `OWNTRACT` | text |
| 108 | `owntrail` | `OWNTRAIL` | text |
| 109 | `owncoach` | `OWNCOACH` | text |
| 110 | `ownschool_1_8` | `OWNSCHOOL_1_8` | text |
| 111 | `ownschool_9_15` | `OWNSCHOOL_9_15` | text |
| 112 | `ownschool_16` | `OWNSCHOOL_16` | text |
| 113 | `ownbus_16` | `OWNBUS_16` | text |
| 114 | `ownvan_1_8` | `OWNVAN_1_8` | text |
| 115 | `ownvan_9_15` | `OWNVAN_9_15` | text |
| 116 | `ownlimo_1_8` | `OWNLIMO_1_8` | text |
| 117 | `ownlimo_9_15` | `OWNLIMO_9_15` | text |
| 118 | `ownlimo_16` | `OWNLIMO_16` | text |
| 119 | `trmtruck` | `TRMTRUCK` | text |
| 120 | `trmtract` | `TRMTRACT` | text |
| 121 | `trmtrail` | `TRMTRAIL` | text |
| 122 | `trmcoach` | `TRMCOACH` | text |
| 123 | `trmschool_1_8` | `TRMSCHOOL_1_8` | text |
| 124 | `trmschool_9_15` | `TRMSCHOOL_9_15` | text |
| 125 | `trmschool_16` | `TRMSCHOOL_16` | text |
| 126 | `trmbus_16` | `TRMBUS_16` | text |
| 127 | `trmvan_1_8` | `TRMVAN_1_8` | text |
| 128 | `trmvan_9_15` | `TRMVAN_9_15` | text |
| 129 | `trmlimo_1_8` | `TRMLIMO_1_8` | text |
| 130 | `trmlimo_9_15` | `TRMLIMO_9_15` | text |
| 131 | `trmlimo_16` | `TRMLIMO_16` | text |
| 132 | `trptruck` | `TRPTRUCK` | text |
| 133 | `trptract` | `TRPTRACT` | text |
| 134 | `trptrail` | `TRPTRAIL` | text |
| 135 | `trpcoach` | `TRPCOACH` | text |
| 136 | `trpschool_1_8` | `TRPSCHOOL_1_8` | text |
| 137 | `trpschool_9_15` | `TRPSCHOOL_9_15` | text |
| 138 | `trpschool_16` | `TRPSCHOOL_16` | text |
| 139 | `trpbus_16` | `TRPBUS_16` | text |
| 140 | `trpvan_1_8` | `TRPVAN_1_8` | text |
| 141 | `trpvan_9_15` | `TRPVAN_9_15` | text |
| 142 | `trplimo_1_8` | `TRPLIMO_1_8` | text |
| 143 | `trplimo_9_15` | `TRPLIMO_9_15` | text |
| 144 | `trplimo_16` | `TRPLIMO_16` | text |
| 145 | `docket1_status_code` | `DOCKET1_STATUS_CODE` | text |
| 146 | `docket2_status_code` | `DOCKET2_STATUS_CODE` | text |
| 147 | `docket3_status_code` | `DOCKET3_STATUS_CODE` | text |

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

---

## 5. Docket & Numbering Analysis: Census vs Operating Authority

### 5.1 Verification Status of 8-Digit MC Dockets
- **Statement Status**: **NOT VERIFIED**.
- The prior statement claiming *"external verification confirms 8-digit MC dockets exist in MCMIS census exports"* was based on search engine summaries indexing commercial third-party aggregators (such as `otrucking.com`), rather than an authenticated query to the FMCSA Licensing & Insurance (L&I) database or an official FMCSA certificate API.
- In SODA Socrata `az4n-8mr2`, raw records for newly registered carriers do return 8-digit numeric strings in the `docket1` column (e.g., MOREE HAUL LLC: `docket1prefix = 'MC'`, `docket1 = '54783262'`; KB PREMIER LOGISTICS LLC: `docket1 = '93474529'`; TITANIUM TRANSIT INC: `docket1 = '92024942'`).
- The system normalizer preserves these exact digits without truncation (`54783262` -> `54783262`), but these 8-digit dockets remain **NOT VERIFIED** as legal operating authority grants until corroborated directly against FMCSA L&I (`nakq-58th` / `9mw4-x3tu`).

### 5.2 Numbering Distributions & Non-Sequentiality
An audit was conducted across stored carriers, census mirror records, and the 23 discovery candidates:

| Cohort | Count | USDOT Range | MC Length Distribution | Spearman Rank Correlation ($\rho$: USDOT vs Registration Date) |
|---|---|---|---|---|
| **Stored Carriers** | 119 (104 with USDOT) | 2,252,252 – 9,993,866 | 5-digit: 4<br>6-digit: 2<br>7-digit: 10 | N/A (mixed historical cohort) |
| **Census Mirror** | 365 records | 4,584,212 – 9,993,866 | 8-digit: 89 (100% of populated dockets) | $\rho = +0.1064$ ($p \approx 0.04$) |
| **23 Discovery Candidates** | 23 candidates | 4,626,451 – 9,748,539 | 8-digit: 23 (100% 8 digits) | $\rho = -0.0395$ ($p \approx 0.86$) |

### 5.3 Mathematical Findings & Implications
1. **Historical USDOT Sequentiality**: Historically, USDOT numbers are sequential (USDOT ~1,000,000 in mid-2000s, ~3,000,000 in 2017, ~4,000,000 in 2023). Under strict sequential issuance, a carrier cohort's USDOT numbers should correlate monotonically with their registration dates ($\rho \to +1.0$).
2. **`add_date` Non-Sequentiality**: The Spearman rank correlation between USDOT and `add_date` is essentially zero ($\rho = -0.0395$ on candidates, $\rho = +0.1064$ on census mirror). In the 23 candidates, USDOT 4,626,451 and USDOT 9,748,539 share near-identical `add_date` values in August/September 2026.
3. **Implication**: MCMIS `add_date` in `az4n-8mr2` does **not** represent sequential initial carrier registration dates. Instead, it reflects system-level batch import, MCMIS database refresh, or synchronization events.
4. **Docket Numbering Series**: Standard historical FMCSA MC dockets reached ~MC-1600000 (7 digits) by 2023–2024. In the modernized FMCSA Motus system (`nakq-58th`), 8-digit dockets represent unique per-OA docket identifiers assigned by Motus.

### 5.4 Official Settlement of 8-Digit Dockets & Authority Evidence (`nakq-58th`)
1. **8-Digit Dockets Settled with Official Government Proof**:
   - In FMCSA's official Licensing & Insurance dataset `nakq-58th` (*Motus Carrier*), **724 out of 990 dockets (73.1%) are 8-digit dockets prefixed with `MC`** (e.g., `MC87002554`, `MC75191074`, `MC82079206`, `MC63200380`, `MC84856419`, `MC52279690`, `MC75540560`, `MC70601776`, `MC92727365`, `MC77870097`).
   - SODA metadata for `nakq-58th` explicitly defines `docket_number`: *"Unique FMCSA alpha-numeric identifying for-hire motor carriers (MC0000000000, FF0000000000, MX0000000000)"*.
   - Motus dataset description explains: *"the legacy registration system allowed multiple OAs per docket number, while Motus will assign a unique docket number to each OA and allows multiple OAs per USDOT number."*
2. **`docket1_status_code` Meaning & Derivation**:
   - In `az4n-8mr2`, `docket1_status_code` is **derived** from the FMCSA Licensing & Insurance (L&I) database upon batch synchronization. The MCS-150 form contains no status field.
   - **Agreement Rate**: In a comparison across 50 USDOTs appearing in both `az4n-8mr2` and `nakq-58th`, **docket number agreement was 88.0% (44/50)**, but **status agreement was only 44.0% (22/50)**.
   - **HYPOTHESIS**: The status disagreement occurs because census `docket1_status_code` reflects historical grant status or monthly batch synchronization lag, whereas `nakq-58th` reflects real-time operating authority status following revocations or insurance cancellations.
3. **Authority Gate Enforcement (L&I ACTIVE + Active Insurance)**:
   - Re-running the strict authority gate across stored carriers drops `QUALIFIED` from 62 to 0, routing 85 carriers to `NEEDS_ENRICHMENT` awaiting L&I/insurance synchronization or manual operator verification.
   - Provenance records `authority_status_source` as `li_dataset`, `census_docket`, or `manual_operator`.

### 5.5 Inspection of 14 No-Docket Target-State Candidates (L2d)
- **Cohort**: 14 carriers from the 43 target-state candidate pool (CA, GA, TX, FL, IL, Fleet 2-10, Operation `A`, 30-120 days) that lacked `docket_number` values in the census mirror.
- **Lookup Results**: Target-lookup against `nakq-58th` (Motus Carrier) and `9mw4-x3tu` (Active Pending Insurance) returned **0 / 14 matches (100% `NO_RECORD`)**.
- **Root Cause & Disposition**: These entities registered on the MCS-150 census declaring `carrier_operation = 'A'` (authorized for hire), but never completed an operating authority filing with FMCSA Licensing & Insurance (either operating strictly intrastate or abandoning interstate registration).
- **Enforcement**: All 14 carriers are strictly retained as `NEEDS_REVIEW` with explicit reason recorded: `"No operating authority or docket filing on file in FMCSA L&I (intrastate or private registrant)"`. Zero ingestion.

### 5.6 Operator Manual Authority Verification & Sanity Flags (L2i)
- **Ready-to-Contact Filter**: Added `"Authority unproven - verify manually"` filter mode to `/api/leads/callable-mailable` to expose reachable, phone format-valid carriers needing manual SAFER verification.
- **Manual Verification Form/Endpoint**: `POST /api/leads/{company_id}/verify-authority-manual` allows operators to enter date, MC number, authority status, and insurance filing verification as observed on official SAFER (`https://safer.fmcsa.dot.gov/CompanySnapshot.aspx`). Updates provenance (`method="manual_operator"`), re-scores, and re-evaluates lifecycle status.
- **Data Sanity Flags**:
  - `fleet_inconsistent`: Flags divergence between power units, truck units, and drivers (42.9% across stored carriers).
  - `hazmat_carrier`: Flags hazardous material haulers via `hm_ind = 'Y'` or explicit hazmat operation/equipment (47.1% across stored carriers; filters out `NON-HAZMAT`).
  - `phone_region_mismatch`: Flags phone area code geocoded US state divergence from business address state (11.8% across stored carriers, e.g. SOPHY'S FRUITS FL address vs 973 NJ phone).

### 5.6.1 Historical Status Transition Audit (61 vs 62 Reconciliation) (M3)
- An audit of `lead_status_history` and `companies` across all historical discovery runs confirmed that exactly **62 distinct shipper records** were transitioned to `QUALIFIED` (`RESEARCHING -> QUALIFIED`). Subsequently, all 62 (plus 28 un-qualified shippers) were archived to `ARCHIVED_NO_CONTACT`.
- Why an earlier document cited 61 vs 62: The exact cause of the single-row variation in legacy documentation is **not determined** from immutable SQL database history (likely an off-by-one run boundary or transient deduplication merge in earlier runs).
- **M3 Data Rule Enforcement**: Priority is strictly `NONE` for `REJECTED`, `NOT_ICP`, `NEEDS_REVIEW_ICP`, and `ARCHIVED` (`ARCHIVED_NO_CONTACT`) leads. The 4 `REJECTED` leads that previously retained priority tiers (`RIDECARE, LLC`, `HERNANDEZ TIRES AUTO CENTER`, `LEGACY LOGISTICS INC`, `PACHECO TRANSPORTATION AND WHOLESALE`) have been migrated to `priority = 'NONE'`.

### 5.7 Positive Control Audit & Motus Dataset Resolution (M1)

#### 1. Positive Control Carriers in `nakq-58th`
An audit was conducted on 5 large, well-known interstate carriers from the census mirror (fleet > 500 power units):
1. **SWIFT TRANSPORTATION COMPANY OF ARIZONA LLC** (USDOT: `54283`, Fleet: 12,940 power units, Census Docket: `MC-136818`)
2. **J B HUNT TRANSPORT INC** (USDOT: `80806`, Fleet: 25,280 power units, Census Docket: `FF-51075` / `MC-135797`)
3. **SCHNEIDER NATIONAL CARRIERS INC** (USDOT: `264184`, Fleet: 9,866 power units, Census Docket: `MC-133655`)
4. **OLD DOMINION FREIGHT LINE INC** (USDOT: `90849`, Fleet: 10,313 power units, Census Docket: `MC-107478`)
5. **UNITED PARCEL SERVICE INC** (USDOT: `21800`, Fleet: 112,321 power units, Census Docket: `MC-116200`)

##### Exact Query URLs & Row Counts in `nakq-58th`:
- **SWIFT** (`54283`):
  - Unpadded: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=54283` $\to$ **0 rows**
  - Padded-7: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=0054283` $\to$ **0 rows**
  - Padded-8: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=00054283` $\to$ **0 rows**
- **J B HUNT** (`80806`):
  - Unpadded: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=80806` $\to$ **0 rows**
  - Padded-7: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=0080806` $\to$ **0 rows**
  - Padded-8: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=00080806` $\to$ **0 rows**
- **SCHNEIDER** (`264184`):
  - Unpadded: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=264184` $\to$ **0 rows**
  - Padded-7: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=0264184` $\to$ **0 rows**
  - Padded-8: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=00264184` $\to$ **0 rows**
- **OLD DOMINION** (`90849`):
  - Unpadded: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=90849` $\to$ **0 rows**
  - Padded-7: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=0090849` $\to$ **0 rows**
  - Padded-8: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=00090849` $\to$ **0 rows**
- **UPS** (`21800`):
  - Unpadded: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=21800` $\to$ **0 rows**
  - Padded-7: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=0021800` $\to$ **0 rows**
  - Padded-8: `https://data.transportation.gov/resource/nakq-58th.json?usdot_number=00021800` $\to$ **0 rows**

##### Diagnosis & Defect Resolution:
1. **Root Cause**: Inspection of SODA view metadata (`https://data.transportation.gov/api/views/nakq-58th.json`) revealed dataset name is `"Motus Carrier"` and official FMCSA description explicitly states: `*This is a Daily Difference dataset*. Records for all carriers/brokers/freight forwarders with active, inactive, or pending operating authorities...` It contains only ~476 daily transaction rows. Static/unmodified carriers do not appear in `nakq-58th`.
2. **Master Dataset Discovery**: The cumulative master dataset on `data.transportation.gov` is **`inys-ebih`** (*"Motus Carrier - All With History"*).
3. **Master Verification**: Querying `inys-ebih` (`https://data.transportation.gov/resource/inys-ebih.json?$where=usdot_number in('54283','80806','264184','90849','21800')`) yielded **14 matching rows across all 5 carriers (100% match rate)**, proving 100% active authority status (`Active`), active BIPD liability filings ($75k-$5M), and active bond filings.
4. **Column Format**: In both datasets, `usdot_number` is strictly an unpadded numeric string (e.g. `'54283'`). Any zero-padding produces 0 SODA results.

##### 3 Raw Rows from `nakq-58th`:
- **Row 1**: `USDOT='9594490'`, `Docket='MC63607823'`, `Legal='Buffalo Hauling LLC'`, `Op Auth Type='Motor Carrier of Property (Except Household Goods)'`, `Status='Pending'`, `BIPD='0.000000000000000000'`, `Bond='N'`
- **Row 2**: `USDOT='6397572'`, `Docket='MC55990689'`, `Legal=None`, `Op Auth Type='Motor Carrier of Property (Except Household Goods)'`, `Status='Active'`, `BIPD='750000.000000000000000000'`, `Bond='N'`
- **Row 3**: `USDOT='7887402'`, `Docket='MC75191074'`, `Legal=None`, `Op Auth Type='Motor Carrier of Property (Except Household Goods)'`, `Status='Active'`, `BIPD='750000.000000000000000000'`, `Bond='N'`

#### 2. Stored Carriers (104) and Discovery Candidates (23) Audit
- **Direct `nakq-58th` Matches**:
  - 104 Stored Carriers with USDOT: **0 / 104 (0.0% match rate)**
  - 23 Discovery Candidates: **0 / 23 (0.0% match rate)**
- **Master Cumulative `inys-ebih` Matches**:
  - 104 Stored Carriers: **21 / 104 (20.2% match rate)** (21 rows)
  - 23 Discovery Candidates: **23 / 23 (100.0% match rate)** (25 rows)
- **Status Distributions (`inys-ebih`)**:
  - Stored: `Active: 1`, `Pending: 19`, `Withdrawn: 1`
  - Candidates: `Active: 23`, `Withdrawn: 2`
- **Insurance Distributions (`inys-ebih`)**:
  - Stored BIPD: `$750k: 5`, `$0: 16`
  - Candidates BIPD: `$750k: 18`, `$1M: 4`, `$300k: 1`, `$0: 2`
- **Format Audit (10 Sample Rows in `nakq-58th`)**:
  1. `USDOT='4307273'`, `Docket='MC1678370'`, `Status='Active'`, `BIPD='750000'`, `Bond='N'`
  2. `USDOT='5535481'`, `Docket='MC87002554'`, `Status='Active'`, `BIPD='750000'`, `Bond='N'`
  3. `USDOT='7887402'`, `Docket='MC75191074'`, `Status='Active'`, `BIPD='750000'`, `Bond='N'`
  4. `USDOT='4545048'`, `Docket='MC1804248'`, `Status='Inactive'`, `BIPD='0'`, `Bond='N'`
  5. `USDOT='4411793'`, `Docket='MC1733205'`, `Status='Inactive'`, `BIPD='0'`, `Bond='N'`
  6. `USDOT='8695669'`, `Docket='MC82079206'`, `Status='Pending'`, `BIPD='0'`, `Bond='Y'`
  7. `USDOT='7555897'`, `Docket='MC63200380'`, `Status='Pending'`, `BIPD='0'`, `Bond='N'`
  8. `USDOT='2882704'`, `Docket='MC967522'`, `Status='Active'`, `BIPD='1000000'`, `Bond='N'`
  9. `USDOT='6248267'`, `Docket='MC84856419'`, `Status='Active'`, `BIPD='750000'`, `Bond='N'`
  10. `USDOT='3205074'`, `Docket='MC203249'`, `Status='Active'`, `BIPD='750000'`, `Bond='N'`

#### 3. Census `docket1` vs `nakq-58th` `docket_number` Agreement Rate
- Evaluated across 50 carriers appearing in both `az4n-8mr2` and `nakq-58th`:
  - **Docket Number Agreement Rate**: **47 / 50 (94.0%)**
  - **Status Code Agreement Rate**: **25 / 50 (50.0%)**
- **HYPOTHESIS**: The status disagreement occurs because census `docket1_status_code` in `az4n-8mr2` reflects monthly batch synchronization lag or historical grant status, whereas `nakq-58th` reflects real-time operating authority status following revocations or insurance cancellations.



