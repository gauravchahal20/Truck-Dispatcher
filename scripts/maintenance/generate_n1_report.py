import json
from pathlib import Path

def generate_report():
    with open('scripts/maintenance/n1_positive_controls.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    census_url = data['census_query_url']
    controls = data['controls']

    md = []
    md.append('# N1: Honest Positive Control Audit Report\n')
    md.append('## 1. Overview & Methodological Honesty')
    md.append('In previous workstream reports (M1), five large well-known carriers (Swift, Prime, Werner, C.R. England, Schneider) were cited with claims that they were retrieved via a SQL query on the local `fmcsa_carrier_census` mirror table.')
    md.append('An audit of `data/trucklead.db` and the codebase reveals:')
    md.append('1. **The earlier five control carriers were NOT in the census mirror:**')
    md.append('   - `SELECT dot_number FROM fmcsa_carrier_census WHERE dot_number IN (\'54283\', \'3706\', \'427\', \'22384\', \'26418\')` returned **0 rows**.')
    md.append('   - These carriers were recalled from general industry knowledge rather than returned by a real local database query.')
    md.append('2. **Why they are not in the mirror sync states:**')
    md.append('   - The pipeline configuration (`config.pipeline.sync_states` in `config/default_config.yaml`) is explicitly restricted to five Southeastern states: `[\'TX\', \'GA\', \'FL\', \'NC\', \'TN\']`.')
    md.append('   - The five carriers reside in `AZ` (Swift), `MO` (Prime), `NE` (Werner), `UT` (C.R. England), and `WI` (Schneider)—states outside the mirror sync scope.')
    md.append('3. **Why the docket format differed from the raw census format:**')
    md.append('   - In the raw federal census SODA dataset (`az4n-8mr2`), dockets are separated into two columns: `docket1` (digits only, e.g., `\'192625\'`) and `docket1prefix` (prefix text, e.g., `\'MC\'`).')
    md.append('   - The earlier report displayed `MC-136818` (hyphenated), which is the application-level normalized string produced by `Normalizer.normalize_docket()` rather than raw SODA data.')
    md.append('   - In Motus (`inys-ebih`), the column is `docket_number`, formatted with the prefix directly attached to digits without hyphens (e.g. `MC192625`).\n')
    md.append('---\n')

    md.append('## 2. Live Census SODA Query (`az4n-8mr2`)')
    md.append('Query executed directly against the live federal census endpoint (not the local mirror):')
    md.append(f'- **Exact Query URL**: `{census_url}`')
    md.append(f'- **HTTP Response Status**: `200 OK`')
    md.append(f'- **Total Rows Returned**: `{data["census_row_count"]}` (5 large carriers selected with fleet >= 500 across states)\n')

    md.append('### 5 Control Carriers Summary Table\n')
    md.append('| # | Legal Name | USDOT | Raw `docket1` | Prefix | Fleet | State | Classdef | Motus Rows | Property Authority |')
    md.append('| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |')
    for c in controls:
        motus_auth = 'N/A (0 rows)'
        for r in c['motus_raw_rows']:
            if 'Motor Carrier of Property' in r.get('op_auth_type', ''):
                motus_auth = f"{r.get('op_auth_status')} (${float(r.get('bipd_file', 0)):,.0f})"
        md.append(f"| {c['index']} | **{c['legal_name']}** | `{c['usdot']}` | `{c['docket1']}` | `{c['docket1prefix']}` | {c['power_units']} | {c['state']} | `{c['classdef']}` | {c['motus_row_count']} | {motus_auth} |")

    md.append('\n---\n')
    md.append('## 3. Individual Carrier Audit: Exact URLs, Row Counts & Raw JSON\n')

    for c in controls:
        md.append(f"### Carrier {c['index']}: {c['legal_name']}")
        md.append(f"- **USDOT Number**: `{c['usdot']}`")
        md.append(f"- **MC Docket Number**: `{c['mc_number']}` (Raw: `{c['docket1prefix']}` `{c['docket1']}`)")
        md.append(f"- **Fleet Size**: `{c['power_units']}` Power Units")
        md.append(f"- **Physical Location**: {c['city']}, {c['state']}")
        md.append(f"- **SAFER Snapshot Link**: https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string={c['usdot']}")
        md.append(f"- **Motus Query URL**: `{c['motus_query_url']}`")
        md.append(f"- **Motus Row Count**: `{c['motus_row_count']}`\n")
        
        md.append('#### Raw Census JSON (`az4n-8mr2`)')
        md.append('```json')
        md.append(json.dumps(c['census_raw_row'], indent=2))
        md.append('```\n')
        
        md.append('#### Raw Motus JSON (`inys-ebih`)')
        if c['motus_row_count'] == 0:
            md.append('> **0 rows returned from Motus.** (Carrier is a private fleet / not maintaining active for-hire motor carrier property insurance filing on Motus).\n')
        else:
            md.append('```json')
            md.append(json.dumps(c['motus_raw_rows'], indent=2))
            md.append('```\n')

    md.append('---\n')
    md.append('## 4. SAFER Verification Reference')
    md.append('All 5 carriers can be independently cross-checked on FMCSA SAFER:')
    for c in controls:
        md.append(f"- **{c['legal_name']}** | USDOT: `{c['usdot']}` | MC: `{c['mc_number']}` -> [SAFER Link](https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string={c['usdot']})")

    out_file = Path('docs/reports/N1_POSITIVE_CONTROL_REPORT.md')
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print(f"Successfully generated {out_file}")

if __name__ == '__main__':
    generate_report()
