# N1: Honest Positive Control Audit Report

## 1. Overview & Methodological Honesty
In previous workstream reports (M1), five large well-known carriers (Swift, Prime, Werner, C.R. England, Schneider) were cited with claims that they were retrieved via a SQL query on the local `fmcsa_carrier_census` mirror table.
An audit of `data/trucklead.db` and the codebase reveals:
1. **The earlier five control carriers were NOT in the census mirror:**
   - `SELECT dot_number FROM fmcsa_carrier_census WHERE dot_number IN ('54283', '3706', '427', '22384', '26418')` returned **0 rows**.
   - These carriers were recalled from general industry knowledge rather than returned by a real local database query.
2. **Why they are not in the mirror sync states:**
   - The pipeline configuration (`config.pipeline.sync_states` in `config/default_config.yaml`) is explicitly restricted to five Southeastern states: `['TX', 'GA', 'FL', 'NC', 'TN']`.
   - The five carriers reside in `AZ` (Swift), `MO` (Prime), `NE` (Werner), `UT` (C.R. England), and `WI` (Schneider)—states outside the mirror sync scope.
3. **Why the docket format differed from the raw census format:**
   - In the raw federal census SODA dataset (`az4n-8mr2`), dockets are separated into two columns: `docket1` (digits only, e.g., `'192625'`) and `docket1prefix` (prefix text, e.g., `'MC'`).
   - The earlier report displayed `MC-136818` (hyphenated), which is the application-level normalized string produced by `Normalizer.normalize_docket()` rather than raw SODA data.
   - In Motus (`inys-ebih`), the column is `docket_number`, formatted with the prefix directly attached to digits without hyphens (e.g. `MC192625`).

---

## 2. Live Census SODA Query (`az4n-8mr2`)
Query executed directly against the live federal census endpoint (not the local mirror):
- **Exact Query URL**: `https://data.transportation.gov/resource/az4n-8mr2.json?%24where=status_code%3D%27A%27+and+docket1+is+not+null+and+%28power_units+like+%27____%25%27+or+power_units+like+%275__%25%27+or+power_units+like+%276__%25%27+or+power_units+like+%277__%25%27+or+power_units+like+%278__%25%27+or+power_units+like+%279__%25%27%29&%24limit=20`
- **HTTP Response Status**: `200 OK`
- **Total Rows Returned**: `20` (5 large carriers selected with fleet >= 500 across states)

### 5 Control Carriers Summary Table

| # | Legal Name | USDOT | Raw `docket1` | Prefix | Fleet | State | Classdef | Motus Rows | Property Authority |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **A D TRANSPORT EXPRESS INC** | `296052` | `192625` | `MC` | 500 | MI | `AUTHORIZED FOR HIRE` | 2 | Active ($1,000,000) |
| 2 | **FISHER AUTO PARTS INC** | `298608` | `99790` | `MC` | 3315 | VA | `PRIVATE PROPERTY;AUTHORIZED FOR HIRE` | 0 | N/A (0 rows) |
| 3 | **RYDER TRANSPORTATION SOLUTIONS LLC** | `299073` | `191394` | `MC` | 4471 | FL | `AUTHORIZED FOR HIRE` | 2 | Active ($1,000,000) |
| 4 | **DOMINO'S PIZZA DISTRIBUTION LLC** | `302173` | `356668` | `MC` | 636 | MI | `PRIVATE PROPERTY;AUTHORIZED FOR HIRE` | 0 | N/A (0 rows) |
| 5 | **KEHE ENTERPRISES LLC** | `302401` | `167130` | `MC` | 735 | FL | `AUTHORIZED FOR HIRE` | 2 | Active ($1,000,000) |

---

## 3. Individual Carrier Audit: Exact URLs, Row Counts & Raw JSON

### Carrier 1: A D TRANSPORT EXPRESS INC
- **USDOT Number**: `296052`
- **MC Docket Number**: `MC-192625` (Raw: `MC` `192625`)
- **Fleet Size**: `500` Power Units
- **Physical Location**: CANTON, MI
- **SAFER Snapshot Link**: https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=296052
- **Motus Query URL**: `https://data.transportation.gov/resource/inys-ebih.json?usdot_number=296052`
- **Motus Row Count**: `2`

#### Raw Census JSON (`az4n-8mr2`)
```json
{
  "mcs150_date": "20260113",
  "add_date": "19870619",
  "status_code": "A",
  "dot_number": "296052",
  "dun_bradstreet_no": "121525026",
  "phy_omc_region": "05",
  "carrier_operation": "A",
  "business_org_id": "3",
  "mcs150_mileage": "42194559",
  "mcs150_mileage_year": "2024",
  "mcs150_update_code_id": "1",
  "phone": "7343977100",
  "company_officer_1": "MATTHEW T PERCY",
  "company_officer_2": "GARY A PERCY",
  "business_org_desc": "CORPORATION",
  "truck_units": "498",
  "power_units": "500",
  "bus_units": "0",
  "fleetsize": "T",
  "carship": "C;B",
  "docket1prefix": "MC",
  "docket1": "192625",
  "docket2prefix": "MC",
  "docket2": "455523",
  "total_intrastate_drivers": "0",
  "hm_ind": "Y",
  "interstate_beyond_100_miles": "411",
  "interstate_within_100_miles": "18",
  "intrastate_beyond_100_miles": "0",
  "intrastate_within_100_miles": "0",
  "total_cdl": "429",
  "total_drivers": "429",
  "classdef": "AUTHORIZED FOR HIRE",
  "legal_name": "A D TRANSPORT EXPRESS INC",
  "phy_street": "5601 BELLEVILLE",
  "phy_city": "CANTON",
  "phy_country": "US",
  "phy_state": "MI",
  "phy_zip": "48188",
  "phy_cnty": "163",
  "carrier_mailing_street": "5601 BELLEVILLE",
  "carrier_mailing_state": "MI",
  "carrier_mailing_city": "CANTON",
  "carrier_mailing_country": "US",
  "carrier_mailing_zip": "48188",
  "carrier_mailing_cnty": "163",
  "driver_inter_total": "429",
  "email_address": "mvonholten@adtransport.com",
  "review_type": "C",
  "review_date": "20140916",
  "safety_rating": "S",
  "safety_rating_date": "20141031",
  "crgo_genfreight": "X",
  "crgo_household": "X",
  "crgo_metalsheet": "X",
  "crgo_liqgas": "X",
  "crgo_grainfeed": "X",
  "crgo_usmail": "X",
  "crgo_chem": "X",
  "crgo_drybulk": "X",
  "crgo_beverages": "X",
  "crgo_paperprod": "X",
  "crgo_cargoothr": "X",
  "crgo_cargoothr_desc": "AUTOMOTIVE",
  "owntract": "51",
  "owntrail": "10",
  "trmtract": "447",
  "trmtrail": "1688",
  "docket1_status_code": "A",
  "docket2_status_code": "I"
}
```

#### Raw Motus JSON (`inys-ebih`)
```json
[
  {
    "docket_number": "MC192625",
    "usdot_number": "296052",
    "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
    "op_auth_status": "Active",
    "min_cov_amount": "1000000.000000000000000000",
    "cargo_req": "N",
    "bond_req": "N",
    "bipd_file": "1000000.000000000000000000",
    "cargo_file": "N",
    "bond_file": "N",
    "bus_undeliverable_mail": "Y",
    "mail_undeliverable_mail": "Y",
    "legal_name": "A D TRANSPORT EXPRESS INC",
    "bus_street_po": "5601 BELLEVILLE",
    "bus_city": "CANTON",
    "bus_state_code": "MI",
    "bus_ctry_code": "US",
    "bus_zip_code": "48188",
    "bus_telno": "7343977100",
    "mail_street_po": "5601 BELLEVILLE",
    "mail_city": "CANTON",
    "mail_state_code": "MI",
    "mail_ctry_code": "US",
    "mail_zip_code": "48188"
  },
  {
    "docket_number": "MC192625",
    "usdot_number": "296052",
    "op_auth_type": "Broker of Property (Except Household Goods)",
    "op_auth_status": "Active",
    "min_cov_amount": "0.000000000000000000",
    "cargo_req": "N",
    "bond_req": "Y",
    "bipd_file": "1000000.000000000000000000",
    "cargo_file": "N",
    "bond_file": "Y",
    "bus_undeliverable_mail": "Y",
    "mail_undeliverable_mail": "Y",
    "legal_name": "A D TRANSPORT EXPRESS INC",
    "bus_street_po": "5601 BELLEVILLE",
    "bus_city": "CANTON",
    "bus_state_code": "MI",
    "bus_ctry_code": "US",
    "bus_zip_code": "48188",
    "bus_telno": "7343977100",
    "mail_street_po": "5601 BELLEVILLE",
    "mail_city": "CANTON",
    "mail_state_code": "MI",
    "mail_ctry_code": "US",
    "mail_zip_code": "48188"
  }
]
```

### Carrier 2: FISHER AUTO PARTS INC
- **USDOT Number**: `298608`
- **MC Docket Number**: `MC-99790` (Raw: `MC` `99790`)
- **Fleet Size**: `3315` Power Units
- **Physical Location**: STAUNTON, VA
- **SAFER Snapshot Link**: https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=298608
- **Motus Query URL**: `https://data.transportation.gov/resource/inys-ebih.json?usdot_number=298608`
- **Motus Row Count**: `0`

#### Raw Census JSON (`az4n-8mr2`)
```json
{
  "mcs150_date": "20260928",
  "add_date": "19870810",
  "status_code": "A",
  "dot_number": "298608",
  "dun_bradstreet_no": "23965379",
  "phy_omc_region": "03",
  "safety_inv_terr": "K",
  "carrier_operation": "A",
  "business_org_id": "3",
  "mcs150_mileage": "8630000",
  "mcs150_mileage_year": "2025",
  "mcs150_update_code_id": "3",
  "phone": "5408858901",
  "fax": "5408859612",
  "company_officer_1": "HERBERT L. GODSCHALK III",
  "company_officer_2": "ARTHUR J. FISHER III",
  "business_org_desc": "CORPORATION",
  "truck_units": "203",
  "power_units": "3315",
  "bus_units": "0",
  "fleetsize": "X",
  "carship": "C;S",
  "docket1prefix": "MC",
  "docket1": "99790",
  "total_intrastate_drivers": "42",
  "hm_ind": "Y",
  "interstate_beyond_100_miles": "119",
  "interstate_within_100_miles": "26",
  "intrastate_beyond_100_miles": "20",
  "intrastate_within_100_miles": "22",
  "total_cdl": "187",
  "total_drivers": "187",
  "classdef": "PRIVATE PROPERTY;AUTHORIZED FOR HIRE",
  "legal_name": "FISHER AUTO PARTS INC",
  "phy_street": "512 GREENVILLE AVE",
  "phy_city": "STAUNTON",
  "phy_country": "US",
  "phy_state": "VA",
  "phy_zip": "24401-4755",
  "phy_cnty": "790",
  "carrier_mailing_street": "PO BOX 2246",
  "carrier_mailing_state": "VA",
  "carrier_mailing_city": "STAUNTON",
  "carrier_mailing_country": "US",
  "carrier_mailing_zip": "24402-2246",
  "carrier_mailing_cnty": "790",
  "driver_inter_total": "145",
  "email_address": "decly@fisherautoparts.com",
  "crgo_cargoothr": "X",
  "crgo_cargoothr_desc": "UNSPECIFIED",
  "owntruck": "165",
  "owntract": "38",
  "owntrail": "62",
  "docket1_status_code": "A"
}
```

#### Raw Motus JSON (`inys-ebih`)
> **0 rows returned from Motus.** (Carrier is a private fleet / not maintaining active for-hire motor carrier property insurance filing on Motus).

### Carrier 3: RYDER TRANSPORTATION SOLUTIONS LLC
- **USDOT Number**: `299073`
- **MC Docket Number**: `MC-191394` (Raw: `MC` `191394`)
- **Fleet Size**: `4471` Power Units
- **Physical Location**: CORAL GABLES, FL
- **SAFER Snapshot Link**: https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=299073
- **Motus Query URL**: `https://data.transportation.gov/resource/inys-ebih.json?usdot_number=299073`
- **Motus Row Count**: `2`

#### Raw Census JSON (`az4n-8mr2`)
```json
{
  "mcs150_date": "20260505",
  "add_date": "19870812",
  "status_code": "A",
  "dot_number": "299073",
  "dun_bradstreet_no": "623077435",
  "phy_omc_region": "05",
  "carrier_operation": "A",
  "business_org_id": "3",
  "mcs150_mileage": "353924923",
  "mcs150_mileage_year": "2025",
  "mcs150_update_code_id": "1",
  "phone": "7862471987",
  "company_officer_1": "ALEJANDRO (ALEX) LLAMA",
  "company_officer_2": "JAMES FINLEY",
  "business_org_desc": "CORPORATION",
  "truck_units": "4471",
  "power_units": "4471",
  "bus_units": "0",
  "fleetsize": "Y",
  "carship": "C;B",
  "docket1prefix": "MC",
  "docket1": "191394",
  "total_intrastate_drivers": "0",
  "mcsipstep": "0",
  "mcsipdate": "20210813",
  "hm_ind": "Y",
  "interstate_beyond_100_miles": "4121",
  "interstate_within_100_miles": "2089",
  "intrastate_beyond_100_miles": "0",
  "intrastate_within_100_miles": "0",
  "total_cdl": "5982",
  "total_drivers": "6210",
  "classdef": "AUTHORIZED FOR HIRE",
  "legal_name": "RYDER TRANSPORTATION SOLUTIONS LLC",
  "dba_name": "RYDER",
  "phy_street": "2333 PONCE DE LEON BLVD SUITE 700",
  "phy_city": "CORAL GABLES",
  "phy_country": "US",
  "phy_state": "FL",
  "phy_zip": "33134",
  "phy_cnty": "086",
  "carrier_mailing_street": "6000 WINDWARD PKWY",
  "carrier_mailing_state": "GA",
  "carrier_mailing_city": "ALPHARETTA",
  "carrier_mailing_country": "US",
  "carrier_mailing_zip": "30005",
  "carrier_mailing_cnty": "121",
  "driver_inter_total": "6210",
  "email_address": "jfinley@ryder.com",
  "review_type": "C",
  "review_date": "20100617",
  "safety_rating": "S",
  "safety_rating_date": "20100622",
  "crgo_genfreight": "X",
  "crgo_household": "X",
  "crgo_metalsheet": "X",
  "crgo_logpole": "X",
  "crgo_produce": "X",
  "crgo_liqgas": "X",
  "crgo_intermodal": "X",
  "crgo_meat": "X",
  "crgo_chem": "X",
  "crgo_drybulk": "X",
  "crgo_coldfood": "X",
  "crgo_beverages": "X",
  "crgo_paperprod": "X",
  "crgo_utility": "X",
  "crgo_farmsupp": "X",
  "trmtruck": "635",
  "trmtract": "3836",
  "trmtrail": "5341",
  "docket1_status_code": "A"
}
```

#### Raw Motus JSON (`inys-ebih`)
```json
[
  {
    "docket_number": "MC191394",
    "usdot_number": "299073",
    "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
    "op_auth_status": "Active",
    "min_cov_amount": "1000000.000000000000000000",
    "cargo_req": "N",
    "bond_req": "N",
    "bipd_file": "1000000.000000000000000000",
    "cargo_file": "N",
    "bond_file": "N",
    "bus_undeliverable_mail": "Y",
    "mail_undeliverable_mail": "Y",
    "dba_name": "Ryder",
    "legal_name": "RYDER TRANSPORTATION SOLUTIONS LLC",
    "bus_street_po": "2333 PONCE DE LEON BLVD SUITE 700",
    "bus_city": "CORAL GABLES",
    "bus_state_code": "FL",
    "bus_ctry_code": "US",
    "bus_zip_code": "33134",
    "bus_telno": "7862471987",
    "mail_street_po": "6000 WINDWARD PKWY",
    "mail_city": "ALPHARETTA",
    "mail_state_code": "GA",
    "mail_ctry_code": "US",
    "mail_zip_code": "30005"
  },
  {
    "docket_number": "MC191394",
    "usdot_number": "299073",
    "op_auth_type": "Broker of Property (Except Household Goods)",
    "op_auth_status": "Active",
    "min_cov_amount": "0.000000000000000000",
    "cargo_req": "N",
    "bond_req": "Y",
    "bipd_file": "1000000.000000000000000000",
    "cargo_file": "N",
    "bond_file": "Y",
    "bus_undeliverable_mail": "Y",
    "mail_undeliverable_mail": "Y",
    "dba_name": "Ryder",
    "legal_name": "RYDER TRANSPORTATION SOLUTIONS LLC",
    "bus_street_po": "2333 PONCE DE LEON BLVD SUITE 700",
    "bus_city": "CORAL GABLES",
    "bus_state_code": "FL",
    "bus_ctry_code": "US",
    "bus_zip_code": "33134",
    "bus_telno": "7862471987",
    "mail_street_po": "6000 WINDWARD PKWY",
    "mail_city": "ALPHARETTA",
    "mail_state_code": "GA",
    "mail_ctry_code": "US",
    "mail_zip_code": "30005"
  }
]
```

### Carrier 4: DOMINO'S PIZZA DISTRIBUTION LLC
- **USDOT Number**: `302173`
- **MC Docket Number**: `MC-356668` (Raw: `MC` `356668`)
- **Fleet Size**: `636` Power Units
- **Physical Location**: ANN ARBOR, MI
- **SAFER Snapshot Link**: https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=302173
- **Motus Query URL**: `https://data.transportation.gov/resource/inys-ebih.json?usdot_number=302173`
- **Motus Row Count**: `0`

#### Raw Census JSON (`az4n-8mr2`)
```json
{
  "mcs150_date": "20260316",
  "add_date": "19870922",
  "status_code": "A",
  "dot_number": "302173",
  "dun_bradstreet_no": "117590320",
  "phy_omc_region": "05",
  "safety_inv_terr": "C",
  "carrier_operation": "A",
  "business_org_id": "3",
  "mcs150_mileage": "43586210",
  "mcs150_mileage_year": "2025",
  "mcs150_update_code_id": "1",
  "phone": "7349303030",
  "company_officer_1": "KERWIN GORDON",
  "company_officer_2": "DANEEN GOSSELIN",
  "business_org_desc": "CORPORATION",
  "truck_units": "636",
  "power_units": "636",
  "bus_units": "0",
  "fleetsize": "U",
  "review_id": "1728099",
  "carship": "C;S",
  "docket1prefix": "MC",
  "docket1": "356668",
  "docket2prefix": "MC",
  "docket2": "1760945",
  "pointnum": "P",
  "total_intrastate_drivers": "0",
  "hm_ind": "N",
  "interstate_beyond_100_miles": "1192",
  "interstate_within_100_miles": "87",
  "intrastate_beyond_100_miles": "0",
  "intrastate_within_100_miles": "0",
  "total_cdl": "1147",
  "total_drivers": "1279",
  "classdef": "PRIVATE PROPERTY;AUTHORIZED FOR HIRE",
  "legal_name": "DOMINO'S PIZZA DISTRIBUTION LLC",
  "dba_name": "DOMINO'S",
  "phy_street": "30 FRANK LLOYD WRIGHT DR",
  "phy_city": "ANN ARBOR",
  "phy_country": "US",
  "phy_state": "MI",
  "phy_zip": "48105",
  "phy_cnty": "161",
  "carrier_mailing_street": "24 FRANK LLOYD WRIGHT DR",
  "carrier_mailing_state": "MI",
  "carrier_mailing_city": "ANN ARBOR",
  "carrier_mailing_country": "US",
  "carrier_mailing_zip": "48105-9484",
  "carrier_mailing_cnty": "161",
  "driver_inter_total": "1279",
  "email_address": "daneen.gosselin@dominos.com",
  "review_type": "C",
  "review_date": "19960801",
  "safety_rating": "S",
  "safety_rating_date": "19960828",
  "crgo_genfreight": "X",
  "crgo_produce": "X",
  "crgo_meat": "X",
  "crgo_chem": "X",
  "crgo_coldfood": "X",
  "crgo_beverages": "X",
  "crgo_paperprod": "X",
  "crgo_cargoothr": "X",
  "crgo_cargoothr_desc": "PIZZA PRODUCTS DOUGH",
  "trmtruck": "87",
  "trmtract": "549",
  "trmtrail": "643",
  "docket1_status_code": "A",
  "docket2_status_code": "I"
}
```

#### Raw Motus JSON (`inys-ebih`)
> **0 rows returned from Motus.** (Carrier is a private fleet / not maintaining active for-hire motor carrier property insurance filing on Motus).

### Carrier 5: KEHE ENTERPRISES LLC
- **USDOT Number**: `302401`
- **MC Docket Number**: `MC-167130` (Raw: `MC` `167130`)
- **Fleet Size**: `735` Power Units
- **Physical Location**: ELKTON, FL
- **SAFER Snapshot Link**: https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=302401
- **Motus Query URL**: `https://data.transportation.gov/resource/inys-ebih.json?usdot_number=302401`
- **Motus Row Count**: `2`

#### Raw Census JSON (`az4n-8mr2`)
```json
{
  "mcs150_date": "20260203",
  "add_date": "19870925",
  "status_code": "A",
  "dot_number": "302401",
  "dun_bradstreet_no": "5437033",
  "phy_omc_region": "05",
  "safety_inv_terr": "A",
  "carrier_operation": "A",
  "business_org_id": "3",
  "mcs150_mileage": "53979195",
  "mcs150_mileage_year": "2025",
  "mcs150_update_code_id": "1",
  "phone": "9048233891",
  "company_officer_1": "JON MOLLMAN",
  "company_officer_2": "GREG A SIKORSKI",
  "business_org_desc": "CORPORATION",
  "truck_units": "735",
  "power_units": "735",
  "bus_units": "0",
  "fleetsize": "U",
  "mail_nationality_indicator": "U",
  "phy_nationality_indicator": "U",
  "carship": "C;B",
  "docket1prefix": "MC",
  "docket1": "167130",
  "total_intrastate_drivers": "0",
  "hm_ind": "N",
  "interstate_beyond_100_miles": "885",
  "interstate_within_100_miles": "0",
  "intrastate_beyond_100_miles": "0",
  "intrastate_within_100_miles": "0",
  "total_cdl": "885",
  "total_drivers": "885",
  "classdef": "AUTHORIZED FOR HIRE",
  "legal_name": "KEHE ENTERPRISES LLC",
  "dba_name": "KEHE DISTRIBUTORS",
  "phy_street": "3800 DEER PARK BLVD",
  "phy_city": "ELKTON",
  "phy_country": "US",
  "phy_state": "FL",
  "phy_zip": "32033",
  "phy_cnty": "109",
  "carrier_mailing_street": "3800 DEER PARK BLVD",
  "carrier_mailing_state": "FL",
  "carrier_mailing_city": "ELKTON",
  "carrier_mailing_country": "US",
  "carrier_mailing_zip": "32033",
  "carrier_mailing_cnty": "109",
  "driver_inter_total": "885",
  "email_address": "greg.sikorski@kehe.com",
  "review_type": "C",
  "review_date": "20070131",
  "safety_rating": "S",
  "safety_rating_date": "20070202",
  "crgo_genfreight": "X",
  "crgo_produce": "X",
  "crgo_intermodal": "X",
  "crgo_meat": "X",
  "crgo_coldfood": "X",
  "crgo_beverages": "X",
  "crgo_paperprod": "X",
  "crgo_cargoothr": "X",
  "crgo_cargoothr_desc": "SPECIALITY FOODS",
  "owntrail": "25",
  "trmtruck": "1",
  "trmtract": "683",
  "trmtrail": "1137",
  "trptract": "51",
  "trptrail": "213",
  "docket1_status_code": "A"
}
```

#### Raw Motus JSON (`inys-ebih`)
```json
[
  {
    "docket_number": "MC167130",
    "usdot_number": "302401",
    "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
    "op_auth_status": "Active",
    "min_cov_amount": "750000.000000000000000000",
    "cargo_req": "N",
    "bond_req": "N",
    "bipd_file": "1000000.000000000000000000",
    "cargo_file": "N",
    "bond_file": "N",
    "bus_undeliverable_mail": "Y",
    "mail_undeliverable_mail": "Y",
    "dba_name": "KEHE DISTRIBUTORS",
    "legal_name": "KEHE ENTERPRISES LLC",
    "bus_street_po": "3800 DEER PARK BLVD",
    "bus_city": "ELKTON",
    "bus_state_code": "FL",
    "bus_ctry_code": "US",
    "bus_zip_code": "32033",
    "bus_telno": "9048233891",
    "mail_street_po": "3800 DEER PARK BLVD",
    "mail_city": "ELKTON",
    "mail_state_code": "FL",
    "mail_ctry_code": "US",
    "mail_zip_code": "32033"
  },
  {
    "docket_number": "MC167130",
    "usdot_number": "302401",
    "op_auth_type": "Broker of Property (Except Household Goods)",
    "op_auth_status": "Inactive",
    "min_cov_amount": "0.000000000000000000",
    "cargo_req": "N",
    "bond_req": "Y",
    "bipd_file": "1000000.000000000000000000",
    "cargo_file": "N",
    "bond_file": "N",
    "bus_undeliverable_mail": "Y",
    "mail_undeliverable_mail": "Y",
    "dba_name": "KEHE DISTRIBUTORS",
    "legal_name": "KEHE ENTERPRISES LLC",
    "bus_street_po": "3800 DEER PARK BLVD",
    "bus_city": "ELKTON",
    "bus_state_code": "FL",
    "bus_ctry_code": "US",
    "bus_zip_code": "32033",
    "bus_telno": "9048233891",
    "mail_street_po": "3800 DEER PARK BLVD",
    "mail_city": "ELKTON",
    "mail_state_code": "FL",
    "mail_ctry_code": "US",
    "mail_zip_code": "32033"
  }
]
```

---

## 4. SAFER Verification Reference
All 5 carriers can be independently cross-checked on FMCSA SAFER:
- **A D TRANSPORT EXPRESS INC** | USDOT: `296052` | MC: `MC-192625` -> [SAFER Link](https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=296052)
- **FISHER AUTO PARTS INC** | USDOT: `298608` | MC: `MC-99790` -> [SAFER Link](https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=298608)
- **RYDER TRANSPORTATION SOLUTIONS LLC** | USDOT: `299073` | MC: `MC-191394` -> [SAFER Link](https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=299073)
- **DOMINO'S PIZZA DISTRIBUTION LLC** | USDOT: `302173` | MC: `MC-356668` -> [SAFER Link](https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=302173)
- **KEHE ENTERPRISES LLC** | USDOT: `302401` | MC: `MC-167130` -> [SAFER Link](https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string=302401)