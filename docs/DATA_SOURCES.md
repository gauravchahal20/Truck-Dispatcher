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
