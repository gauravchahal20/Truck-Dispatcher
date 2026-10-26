# N4: Dry-Run Evaluation for the 23 Candidates (No Ingestion)

## 1. Compliance Notice & Strict Gating
> [!IMPORTANT]
> **ZERO INGESTION COMPLIANCE**: In accordance with explicit user instructions, **NONE** of the 23 candidate carriers have been ingested into `companies` or `leads`. All 23 carriers remain strictly isolated in the staging table `candidate_watchlist`.

> Ingestion will remain blocked until the user reviews and provides explicit written approval of this dry-run table.

---

## 2. Dry-Run Audit Table (23 Candidate Carriers)

| # | USDOT | Company Legal Name | MC Docket | Motus Auth | Insurance | BIPD ($) | Phone Area vs State Check | Fleet Inconsistency | Hazmat | Email Tier | Principal Officer |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `4626451` | J & A FREIGHT SOLUTIONS LLC | `46000499` | **ACTIVE** | `ACTIVE` | $750,000 | MISMATCH (TX vs GA) | NO | NO | `Generic (Free Webmail)` | Jill Schwear |
| 2 | `5397412` | KB PREMIER LOGISTICS LLC | `93474529` | **ACTIVE** | `PARTIAL` | $300,000 | MATCH | YES | NO | `Named / Corporate` | Kieona Britton |
| 3 | `5576599` | RFM LOGISTICS LLC | `99004685` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Role-based` | Filip Ratkovic |
| 4 | `5624791` | MCCORD PREMIER LOGISTICS | `96662348` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | Bernita McCord |
| 5 | `5800824` | NORTHAMPTON LOGISTICS LLC | `73223354` | **ACTIVE** | `ACTIVE` | $750,000 | MISMATCH (WA vs GA) | NO | NO | `Generic (Free Webmail)` | Umaru Ntambi |
| 6 | `6089086` | KEEP IT EASY LOGISTICS LLC | `48964405` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | MICHAEL WILLIN |
| 7 | `6933041` | R&K FREIGHT SOLUTIONS LLC | `72632298` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Role-based` | Rendale McClendon |
| 8 | `7311877` | LIN VENTURES LLC | `71861465` | **ACTIVE** | `ACTIVE` | $750,000 | MISMATCH (TX vs GA) | NO | NO | `Generic (Free Webmail)` | HUAHONG LIN |
| 9 | `7637833` | TC GLOBAL EXPRESS CORP. | `59355007` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | Tomasz Chodorowski |
| 10 | `7924740` | COAST 2 COAST LLC | `71443231` | **ACTIVE** | `ACTIVE` | $1,000,000 | MATCH | NO | NO | `Generic (Free Webmail)` | Unubold Tsolmon |
| 11 | `8040909` | LORENTE TRANSPORTATION LLC | `83252390` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | YIMI PEREZ LORENTE |
| 12 | `8220775` | THE HARRIETTE LLC | `85320894` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | Bryan Harriette Marks |
| 13 | `8288381` | HUSKY SERVICES INC | `93713497` | **ACTIVE** | `ACTIVE` | $1,000,000 | MATCH | NO | NO | `Generic (Free Webmail)` | SADI HUSSEIN |
| 14 | `8295005` | LEAPFREIGHT CARRIER GROUP LL | `76299418` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Named / Corporate` | Robert Angrish |
| 15 | `8718734` | MOREE HAUL LLC | `54783262` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | mustafa osman |
| 16 | `8734003` | MM INTERNATIONAL LLC | `98190725` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | DIANA MILUTINOVIC |
| 17 | `8903053` | TITANIUM TRANSIT INC | `92024942` | **ACTIVE** | `ACTIVE` | $1,000,000 | MATCH | NO | NO | `Role-based` | Zaynitdin Inoyatov |
| 18 | `8972558` | AMERICAN TRUST LOGISTICS INC | `75017222` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Named / Corporate` | GULNOZA YUNUSOVA |
| 19 | `9340484` | ROUTEX LOGISTICS LLC | `80765209` | **ACTIVE** | `ACTIVE` | $750,000 | MISMATCH (CA vs IL) | NO | NO | `Generic (Free Webmail)` | IGOR MARCHUK |
| 20 | `9348731` | TL WAY EXPRESS LLC | `85450220` | **ACTIVE** | `ACTIVE` | $1,000,000 | MISMATCH (NJ vs IL) | NO | NO | `Generic (Free Webmail)` | Nineli Gabelaia |
| 21 | `9607661` | OMA GOLD INC. | `60753181` | **ACTIVE** | `ACTIVE` | $750,000 | MISMATCH (WA vs IL) | NO | NO | `Generic (Free Webmail)` | MURATBEK AITEMIROV |
| 22 | `9737844` | JLM HOLDING COMPANY INC | `50652037` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | Joshua McClain |
| 23 | `9748539` | JJCK INC | `93373593` | **ACTIVE** | `ACTIVE` | $750,000 | MATCH | NO | NO | `Generic (Free Webmail)` | ROBERT HORTILLAS |

---

## 3. Summary Hygiene & Quality Metrics

- **Total Watchlist Candidates**: **23**
- **Operating Authority**: **23 / 23 (100%) ACTIVE** Motor Carrier of Property in Motus (`inys-ebih`).
- **Insurance Filing Status**:
  - **ACTIVE** ($750k - $1M BIPD on file): **22 carriers** (95.7%)
  - **PARTIAL** ($300k BIPD on file): **1 carrier** (`5397412`, KB Premier Logistics LLC)
- **Phone Region Mismatches**: **6** carriers (26.1%) have telephone area codes outside their registered physical domicile state.
- **Fleet Inconsistency**: **1** carrier (`5397412`, 1 power unit vs 0 drivers discrepancy).
- **Hazmat Indicators**: **0** carriers (0% hazmat; clean general freight).
- **Census Email Coverage by Tier**:
  - `Generic (Free Webmail)`: **17 carriers** (73.9%)
  - `Named / Corporate`: **3 carriers** (13.0%)
  - `Role-based`: **3 carriers** (13.0%)

---

## 4. Proposed Ingestion Architecture: `recent_registration` Segment

To prevent dilution of our mature carrier pool, we propose ingesting these 23 carriers as an isolated segment:

1. **Segment Tag**: `lead_source = 'recent_registration'` (distinct from `fmcsa_safer` and `census_mirror`).
2. **Signal Attribution**: Assign signal `NEW_USDOT_REGISTRATION`:
   - **Config Weight**: `0.5` intent points (conservative, small weight so it does not falsely overpower core fit score).
   - **Half-Life**: `60.0` days exponential decay.
   - **Evidence Tag**: `az4n-8mr2` registration add_date with target cohort tag `recent_registration`.
3. **Gate Status on Ingestion**:
   - Carriers passing fit score >= 5.0 and BIPD >= $750k will enter `QUALIFIED` / `FINAL`.
   - KB Premier Logistics ($300k BIPD) will route to `NEEDS_ENRICHMENT` (insufficient insurance).
4. **Approval Block**:

   - Status: **AWAITING USER APPROVAL** before any insert operation is executed.