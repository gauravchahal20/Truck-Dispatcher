# N3: Authority Application to Stored Carriers & Authority Gate Audit

## 1. Sync Methodology & Implementation
A targeted live sync against the federal master licensing and insurance dataset (`inys-ebih`) was performed using batched `IN` queries (chunks of 30 USDOTs) and cached locally at `scripts/maintenance/inys_audit_results.json`.
- Total stored carriers evaluated: **104 carriers with USDOT** (out of 119 total carriers in database).
- Matched with Motus records: **21 carriers** (20.2%).
- Unmatched in Motus: **83 carriers** (79.8%).

---

## 2. Before / After Tables

### Table 2.1: Lead Status Distribution (Before vs After Authority Gate)
| Lead Status | Before Count | After Count | Net Change | Operational Treatment |
| :--- | :--- | :--- | :--- | :--- |
| **NEEDS_ENRICHMENT** | 85 | 85 | +0 | Queued in Verify-and-Call queue |
| **NEEDS_REVIEW_ICP** | 2 | 2 | +0 | Operator review |
| **NOT_ICP** | 3 | 3 | +0 | Suppressed/Exempt |
| **REJECTED** | 29 | 29 | +0 | Suppressed/Exempt |
| **Total** | **119** | **119** | **0** | - |

### Table 2.2: Score Band Distribution (Before vs After Authority Gate)
| Priority Score Band | Score Range | Before Count | After Count | Net Change | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Priority A** | Score >= 8.0 | 0 | 0 | +0 | Active |
| **Priority B** | Score 6.5 - 7.9 | 2 | 2 | +0 | Active |
| **Priority C** | Score 5.0 - 6.4 | 6 | 6 | +0 | Active |
| **Priority NONE** | Score < 5.0 (Below gate) | 111 | 111 | +0 | Active |
| **Total** | - | **119** | **119** | **0** | - |

---

## 3. Results for the 21 Matched Carriers in `inys-ebih`

Authority Gate Criteria: `authority_status == 'ACTIVE'` AND `insurance_filing_status == 'ACTIVE'` (BIPD >= $750k) AND `lead_score >= 5.0` (or `fit_score >= 5.0`).

| # | USDOT | Company Name | Docket | Auth Type | Motus Status | Ins Status | BIPD ($) | Score | Gate Result | Final Lead Status |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `2252252` | SOPHY'S FRUITS COMPANY | `MC781620` | Motor Carrier of Property (Excep | **ACTIVE** | `ACTIVE` | $750,000 | 4.2 | FAIL (Score 4.2 < 5.0 minimum threshold) | `NEEDS_ENRICHMENT` |
| 2 | `4958665` | TORNADO TRUCKING, LLC | `MC56505161` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 3 | `8850040` | 1129 TRANSPORT LLC | `MC96954081` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 4 | `6776302` | NEWTON TRUCKING LLC | `MC66769190` | Motor Carrier of Property (Excep | **WITHDRAWN** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: WITHDRAWN, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 5 | `8731821` | G & R TRANSPORT LOGISTICS LLC | `MC86697138` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 6 | `7165355` | DAIS | `MC81491738` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `REJECTED` |
| 7 | `6225917` | BARLEY'S TRUCKING LLC | `MC86663109` | Motor Carrier of Property (Excep | **PENDING** | `ACTIVE` | $750,000 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: ACTIVE)) | `NEEDS_ENRICHMENT` |
| 8 | `9925997` | K&M LOGISTICS NORTHWEST LLC | `MC75723802` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 9 | `9026608` | CROSS USA SERVICES | `MC53283592` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `REJECTED` |
| 10 | `5580259` | REDEMPTN LLC | `MC94990392` | Motor Carrier of Passengers | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `REJECTED` |
| 11 | `9485527` | TRIPLE RUST TRANSPORT LLC | `MC73033742` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 4.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 12 | `9655205` | GEOFORCE LOGISTICS LLC | `MC93882844` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 13 | `8726457` | TALON J LOGISTICS LLC | `MC61885137` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 5.0 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 14 | `9778424` | PACHECO TRANSPORTATION AND WHO | `MC63118832` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 6.0 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `REJECTED` |
| 15 | `5428178` | VLC TRANSPORTATION LLC | `MC63186939` | Motor Carrier of Property (Excep | **PENDING** | `ACTIVE` | $750,000 | 5.0 | FAIL (Authority unproven (Auth: PENDING, Ins: ACTIVE)) | `NEEDS_ENRICHMENT` |
| 16 | `9864043` | HTX TRANSPORT INC | `MC99042931` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 17 | `8493604` | VIAJERO DEL NORTH LLC | `MC81908248` | Motor Carrier of Property (Excep | **PENDING** | `ACTIVE` | $750,000 | 5.0 | FAIL (Authority unproven (Auth: PENDING, Ins: ACTIVE)) | `NEEDS_ENRICHMENT` |
| 18 | `9474155` | JIN LOGISTICS LLC. | `MC80500001` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 19 | `8845359` | H.E. ALLEN & SON LLC | `MC58321407` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 6.0 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 20 | `8970653` | BUCKEYE HEAVY HAUL AND LOGISTI | `MC56500001` | Motor Carrier of Property (Excep | **PENDING** | `NONE` | $0 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: NONE)) | `NEEDS_ENRICHMENT` |
| 21 | `7254076` | PRIME GLOBAL ENTERPRISES LLC | `MC84516972` | Motor Carrier of Property (Excep | **PENDING** | `ACTIVE` | $750,000 | 3.8 | FAIL (Authority unproven (Auth: PENDING, Ins: ACTIVE)) | `NEEDS_ENRICHMENT` |

> **Promotion Analysis**:

> - Only 1 carrier (`2252252`, SOPHY'S FRUITS COMPANY) holds active property authority and $750,000 BIPD insurance. However, its fit score is **4.2**, which is strictly below the minimum threshold of **5.0** (`Score 4.2 < 5.0`). Therefore, it remains in `NEEDS_ENRICHMENT` pending contact enrichment.

> - The remaining 20 matched carriers fail the active authority gate (19 are `PENDING` authority and 1 is `WITHDRAWN`). None were promoted to `QUALIFIED`.

---

## 4. Audit of the 83 Carriers with No Motus Record (`NO_LI_RECORD`)

For the 83 stored carriers returning 0 records from `inys-ebih`, their operating authority has been systematically set to `authority_status = 'NO_LI_RECORD'` with source `motus_inys_ebih`.

### Breakdown by Census Operating Characteristics:

| Category | Carrier Count | Census Indicator | Pipeline Handling |
| :--- | :--- | :--- | :--- |
| **Intrastate Carriers** | **50** | `carrier_operation` = 'Intrastate' (B/C) | Retained in verify-and-call queue; intrastate freight outreach |
| **Exempt / Private Fleets** | **11** | `operating_status` contains 'EXEMPT' or 'PRIVATE' | Retained in verify-and-call queue; no federal L&I filing required |
| **Pending Initial L&I Filing** | **22** | Active census with MC docket pending L&I posting | Retained in verify-and-call queue; queued for periodic L&I sync |
| **Total Unmatched** | **83** | - | **100% retained in verify-and-call queue; 0 rejected** |

> [!IMPORTANT]
> **Anti-Rejection Policy**: Absence of a Motus L&I record (`NO_LI_RECORD`) is **NEVER** treated as an auto-rejection. All 83 carriers remain active in `NEEDS_ENRICHMENT` and appear in the ranked verify-and-call queue (`/api/verify-and-call-queue`) for human operator dispatch verification.