# N2: Motus Aggregation Rules & Operating Authority Resolution Audit

## 1. Multi-Row Reduction Logic & Aggregation Rules
In FMCSA licensing & insurance filings (`inys-ebih`), a single carrier (USDOT) frequently has multiple active or historical filings covering distinct authority types (Property, Household Goods, Passenger, Broker, Freight Forwarder) and dockets. Reducing these to an authoritative single operating status follows strict domain rules implemented in [`backend/app/services/fmcsa_motus_aggregator.py`](../../backend/app/services/fmcsa_motus_aggregator.py):

1. **Property Authority Priority & Exclusions**:
   - Primary target: `Motor Carrier of Property (Except Household Goods)`.
   - **Exclusions**: Pure broker filings (`Broker of Property`) and freight forwarder filings (`Freight Forwarder of Property`) are strictly excluded from motor carrier property authority. A carrier holding only broker authority cannot legally transport freight under our motor carrier pipeline.
   - Secondary passenger and household goods filings are evaluated only if no general freight property filings exist.
2. **Multiple Dockets / Filings Resolution**:
   - If multiple filings exist for the same carrier (e.g. USDOT 9737844 holds 1 property docket and 2 household goods dockets), the property filing takes precedence.
   - Status resolution hierarchy: `Active` (rank 4) > `Pending` (rank 3) > `Inactive` (rank 2) > `Withdrawn` / `Revoked` (rank 1).
3. **Insurance BIPD Gate**:
   - Property freight carriers require a minimum of $750,000 public liability and property damage (BIPD) insurance filing (`bipd_file >= 750000.0`).
   - Classified into: `ACTIVE` (>= $750k), `PARTIAL` ($1-$749k), or `NONE` ($0).
4. **Missing Records (`NO_LI_RECORD`)**:
   - If a carrier has 0 rows in `inys-ebih`, their status is set to `NO_LI_RECORD`. They are kept in the verify-and-call queue and are never auto-rejected (many are legitimate intrastate or exempt carriers).

---

## 2. Overall `op_auth_status` Distribution Across All Rows (990 Total Rows)

Across all 990 rows in the Motus master mirror (`fmcsa_motus_carrier`):

| Operating Authority Status (`op_auth_status`) | Total Rows | Percentage |
| :--- | :--- | :--- |
| **Active** | 445 | 44.9% |
| **Pending** | 317 | 32.0% |
| **Inactive** | 199 | 20.1% |
| **Withdrawn** | 29 | 2.9% |
| **Total** | **990** | **100.0%** |

### Detailed Distribution by Authority Type

| Authority Type (`op_auth_type`) | Status | Row Count |
| :--- | :--- | :--- |
| `Broker of Household Goods` | `Pending` | 1 |
| `Broker of Property (Except Household Goods)` | `Pending` | 20 |
| `Broker of Property (Except Household Goods)` | `Active` | 19 |
| `Broker of Property (Except Household Goods)` | `Inactive` | 7 |
| `Broker of Property (Except Household Goods)` | `Withdrawn` | 1 |
| `Enterprise Motor Carrier of Property (Except Household Goods)` | `Pending` | 3 |
| `Enterprise Motor Carrier of Property (Except Household Goods)` | `Inactive` | 1 |
| `Enterprise Motor Carrier of Property (Except Household Goods)` | `Active` | 1 |
| `Freight Forwarder of Household Goods` | `Pending` | 2 |
| `Freight Forwarder of Property (Except Household Goods)` | `Pending` | 5 |
| `Freight Forwarder of Property (Except Household Goods)` | `Active` | 2 |
| `Freight Forwarder of Property (Except Household Goods)` | `Withdrawn` | 1 |
| `Mexico Domiciled Motor Carrier of Property (Except Household Goods)` | `Pending` | 1 |
| `Mexico Domiciled Private Motor Carrier of Property (Except Household Goods)` | `Active` | 1 |
| `Motor Carrier of Household Goods` | `Pending` | 14 |
| `Motor Carrier of Household Goods` | `Inactive` | 2 |
| `Motor Carrier of Household Goods` | `Withdrawn` | 1 |
| `Motor Carrier of Household Goods` | `Active` | 1 |
| `Motor Carrier of Passengers` | `Active` | 9 |
| `Motor Carrier of Passengers` | `Pending` | 3 |
| `Motor Carrier of Passengers` | `Withdrawn` | 1 |
| `Motor Carrier of Passengers` | `Inactive` | 1 |
| `Motor Carrier of Property (Except Household Goods)` | `Active` | 412 |
| `Motor Carrier of Property (Except Household Goods)` | `Pending` | 268 |
| `Motor Carrier of Property (Except Household Goods)` | `Inactive` | 188 |
| `Motor Carrier of Property (Except Household Goods)` | `Withdrawn` | 25 |

---

## 3. 50 Compared Carriers: Census Status vs Motus Status Table

Cross-tabulation comparing federal census docket status (`docket1_status_code`) vs live Motus authority status (`op_auth_status`) for 50 distinct carriers:

| Census Status | Motus Status | Count | Interpretation |
| :--- | :--- | :--- | :--- |
| `A` (Active) | `Active` | 25 (50.0%) | Validated active authority and current filings |
| `A` (Active) | `Inactive` | 23 (46.0%) | **Census stale/unrevoked**: Carrier active in census but insurance/authority revoked in L&I |
| `A` (Active) | `Pending` | 2 (4.0%) | Application in progress; not yet operating |

### Detailed Table for all 50 Compared Carriers

| # | USDOT | Carrier Legal Name | Census Docket | Census Status | Motus Docket | Motus Auth Type | Motus Status | BIPD Filing | Agreement |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `1012902` | MAYFIELD'S GARAGE & WRECKER SERVICE INC | `MC1724604` | `A` | `MC1724604` | Motor Carrier of Property (Except H | **Active** | $1,000,000 | YES |
| 2 | `1130476` | ISAAC CREED CATRON | `MC460710` | `A` | `MC460710` | Motor Carrier of Property (Except H | **Inactive** | $1,000,000 | NO (Mismatch) |
| 3 | `1176088` | BISHOP BROTHERS CONSTRUCTION CO INC | `MC599485` | `A` | `MC599485` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 4 | `1189941` | MIGUEL A ALVAREZ | `MC475208` | `A` | `MC475208` | Motor Carrier of Property (Except H | **Active** | $1,000,000 | YES |
| 5 | `1261886` | ALLACO TOWING SERVICE INC | `MC522247` | `A` | `MC522247` | Motor Carrier of Property (Except H | **Inactive** | $1,000,000 | NO (Mismatch) |
| 6 | `1305307` | LA CANADA EXPRESS LLC | `MC506252` | `A` | `MC506252` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 7 | `1387616` | WESTERN MOTORCOACH INC | `MC528470` | `A` | `MC528470` | Motor Carrier of Passengers | **Active** | $5,000,000 | YES |
| 8 | `1416207` | TGM TRUCKING INC | `MC535988` | `A` | `MC535988` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 9 | `1614360` | DIAMOND G TRUCKING LLC | `MC596777` | `A` | `MC596777` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 10 | `1622092` | GGLN LLC | `MC1733047` | `A` | `MC1733047` | Motor Carrier of Property (Except H | **Inactive** | $1,000,000 | NO (Mismatch) |
| 11 | `1633919` | RAVNEET S GILL | `MC602439` | `A` | `MC602439` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 12 | `1642929` | COMBS TRANSPORT LLC | `MC605210` | `A` | `MC605210` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 13 | `1643659` | 915 HAULER INC | `MC90164847` | `A` | `MC90164847` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 14 | `1697743` | HURST HAUL'N LLC | `MC623313` | `A` | `MC623313` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 15 | `1727267` | ELLISON MOTOR CARRIERS LLC | `MC632948` | `A` | `MC632948` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 16 | `1743855` | NIKSTER TRANSPORT LLC | `MC638557` | `A` | `MC638557` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 17 | `1761730` | VC LOGISTICS LLC | `MC619140` | `A` | `MC619140` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 18 | `1794713` | SERVANT TRUCKING LLC | `MC653658` | `A` | `MC653658` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 19 | `1846215` | EAGLES TRADE HOUSE LTD | `MC668700` | `A` | `MC668700` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 20 | `1863719` | K EXPRESS LLC | `MC712046` | `A` | `MC712046` | Motor Carrier of Property (Except H | **Active** | $1,000,000 | YES |
| 21 | `1888770` | TANNER TRUCKING LLC | `MC61676621` | `A` | `MC61676621` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 22 | `1951230` | T S T CARGO INC | `MC698387` | `A` | `MC698387` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 23 | `2009408` | LUIS E GARCIA CONTRERAS | `MC913367` | `A` | `MC913367` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 24 | `2236619` | SUN CITY GROUP LLC | `MC564481` | `A` | `FF55811027` | Freight Forwarder of Property (Exce | **Active** | $0 | YES |
| 25 | `2304671` | TAG DME INC | `MC56665299` | `A` | `MC56665299` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 26 | `2366406` | WINWAY EXPRESS INC | `MC863855` | `A` | `MC863855` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 27 | `2409484` | ALLEN KEY TRANSPORTATION LLC | `MC911925` | `A` | `MC911925` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 28 | `2428609` | MONTOYA TRANSPORT LLC | `MC1731074` | `A` | `MC1731074` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 29 | `2442415` | STAY UP TOWING LLC | `MC49946896` | `A` | `MC49946896` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 30 | `2461027` | CHEETHA INC | `MC86959797` | `A` | `MC86959797` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 31 | `2518020` | R AND J DIRTWORKS INC | `MC1356444` | `A` | `MC1356444` | Motor Carrier of Property (Except H | **Inactive** | $1,000,000 | NO (Mismatch) |
| 32 | `2585739` | FORWARD EXPRESS TRANSPORTATION LLC | `MC906143` | `A` | `MC906143` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 33 | `2593305` | DIGGERS TOWING & AUTO REPAIR LLC | `` | `` | `MC87470071` | Motor Carrier of Property (Except H | **Pending** | $0 | NO (Mismatch) |
| 34 | `2635403` | MANUEL GILBERTO ORTEGA CARDENAS OR PERLA CAROL MENDOZA ESPINOZA | `MC99127268` | `A` | `MC99127268` | Motor Carrier of Property (Except H | **Active** | $1,000,000 | YES |
| 35 | `263622` | FOSTER FUELS LLC | `MC1629107` | `A` | `MC295289` | Motor Carrier of Property (Except H | **Active** | $5,000,000 | YES |
| 36 | `2638185` | SPT TRANSPORT LLC | `MC919062` | `A` | `MC919062` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 37 | `2744361` | MCN LOGISTICS INC | `MC46496` | `A` | `MC46496` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 38 | `2765119` | E.R. VELIZ TRUCKING LLC | `MC1651333` | `A` | `MC1651333` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 39 | `2788182` | NORTH AMERICAN DISTRIBUTION LOG INC | `MC886305` | `A` | `MC886305` | Broker of Property (Except Househol | **Inactive** | $0 | NO (Mismatch) |
| 40 | `2821656` | BEE'S TRANSPORT LLC | `MC1068797` | `A` | `MC1068797` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 41 | `2835111` | INNOVATION WITH GREEN LLC | `MC948419` | `A` | `MC948419` | Motor Carrier of Property (Except H | **Inactive** | $750,000 | NO (Mismatch) |
| 42 | `2846701` | 911 AUTO MOVERS LLC | `MC954588` | `A` | `MC954588` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 43 | `2858092` | AMERICAN TRANSPORTS EXPRESS LLC | `MC957026` | `A` | `MC957026` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 44 | `2882704` | EASTERN TOWING LLC | `MC967522` | `A` | `MC967522` | Motor Carrier of Property (Except H | **Active** | $1,000,000 | YES |
| 45 | `2903382` | MADJIM INC | `MC64606535` | `A` | `MC64606535` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 46 | `2929438` | DK TRUCKIN LLC | `MC988911` | `A` | `MC988911` | Motor Carrier of Property (Except H | **Inactive** | $1,000,000 | NO (Mismatch) |
| 47 | `2930800` | CLARKE TRUCKING LLC | `MC989584` | `A` | `MC989584` | Motor Carrier of Property (Except H | **Active** | $1,000,000 | YES |
| 48 | `2932084` | HIGH FIVE LOGISTICS LLC | `MC990168` | `A` | `MC990168` | Motor Carrier of Property (Except H | **Active** | $750,000 | YES |
| 49 | `2933023` | JL TRANSPORT USA LLC | `MC992524` | `A` | `MC992524` | Motor Carrier of Property (Except H | **Inactive** | $0 | NO (Mismatch) |
| 50 | `2934017` | WALKERS TRUCKING INC | `MC991106` | `A` | `MC991106` | Motor Carrier of Property (Except H | **Pending** | $750,000 | NO (Mismatch) |

---

## 4. Explanation of the Earlier '100% ACTIVE' Claim in Both Cohorts

In Workstream M1, an earlier claim asserted that both the 21 matched stored carriers and the 23 watchlist candidates were '100% ACTIVE' in Motus. Here is the forensic explanation of why that claim was inaccurate:

### 1. Watchlist Candidates Cohort (23 Candidates): Real 100% Active Property Authority
- The 23 watchlist candidates were generated from recently granted authorities. In `inys-ebih`, all 23 carriers indeed hold `op_auth_status = 'Active'` under `Motor Carrier of Property (Except Household Goods)`.
- 22 hold full BIPD insurance ($750k–$1M), and 1 holds partial insurance ($300k, KB Premier Logistics LLC).
- Distribution: **Active: 23/23 (100%)**.

### 2. Stored Carriers Cohort (21 Matched Carriers): False 100% Claim
- In reality, when querying `inys-ebih` with batched live queries for the 21 matched stored carriers:
- **Active**: **1 carrier** (`2252252`, SOPHY'S FRUITS COMPANY) — **4.8%**
- **Pending**: **19 carriers** — **90.5%** (e.g., USDOT 8850040, 6225917, 7165355, 8731821, etc.)
- **Withdrawn**: **1 carrier** (`6776302`, Newton Trucking LLC) — **4.8%**
- **Root cause of earlier error**: The M1 report erroneously assigned `ACTIVE` to all 21 matched stored carriers without inspecting the individual `op_auth_status` field returned by Motus, incorrectly conflating 'presence of an L&I record' with 'active operating authority'.
- Under the honest aggregation rules, **only 1 of the 21 matched stored carriers has ACTIVE property authority**.