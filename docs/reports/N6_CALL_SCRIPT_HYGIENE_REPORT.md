# N6: Factual Call Script & Sender Identity Gating Audit

## 1. Executive Summary & Policy Compliance
In compliance with user directive N6, the call script generator in [`backend/app/api/routes_outcomes.py`](../../backend/app/api/routes_outcomes.py) has been completely refactored to eliminate unverified freight claims and placeholder company entities:
1. **Removed Misleading Freight Claims**:
   - The phrase `"We have immediate freight volume in {state_phrase}."` has been completely deleted.
2. **Factual Dispatch Value Proposition**:
   - The script factually declares what is being offered: `"We provide dispatch support and load booking assistance for small carriers."`
3. **Sender Identity Dynamic Gating**:
   - Caller name and dispatch business entity are dynamically pulled from `config.compliance.sender_identity`.
   - **No placeholder company names**: Placeholder strings (such as `"TruckLead Logistics"`) have been removed from the application.
   - **Gated Script Display**: When `config.compliance.sender_identity` is unset (empty string or None), `call_script` evaluates to `None`, and `script_status` is returned as `"hidden: sender_identity not set"`.
4. **Structured Operational Flow**:
   - Asks for the decision-maker: `"Am I speaking with the person who handles dispatch and freight operations for your fleet?"`
   - Asks about MC operating authority and open fleet capacity: `"Can you confirm if you currently have active interstate MC operating authority and open capacity on {fleet_phrase}?"`
   - Explicit opt-out offering: `"Also, if you're not interested in dispatch assistance, just let me know and I will remove you from our call list immediately."`

---

## 2. Script Comparative Analysis

| Feature | Legacy Script (Workstream M6) | Compliant Script (Workstream N6) |
| :--- | :--- | :--- |
| **Sender Identity** | Hardcoded `"Dispatch at TruckLead Logistics"` | Dynamic `{config.compliance.sender_identity}` |
| **Unset Identity Gating** | Displayed placeholder company | **Hidden (`call_script = None`)** |
| **Freight Volume Claim** | `"We have immediate freight volume"` (False/Unverified) | **Removed completely** |
| **Service Offering** | Unstated / implied freight broker | **Factual**: `"dispatch support and load booking assistance for small carriers"` |
| **Decision-Maker Query** | None (assumed officer) | `"Am I speaking with the person who handles dispatch and freight operations for your fleet?"` |
| **Authority & Capacity** | `"confirm active interstate MC operating authority and open capacity"` | Retained and verified |
| **Opt-Out Offering** | None | `"if you're not interested in dispatch assistance, just let me know and I will remove you from our call list immediately."` |

---

## 3. Verbatim Script Output Example

### When `config.compliance.sender_identity = "Alex Turner with Summit Dispatch"`:
> *"Hello Sarah Connor, this is Alex Turner with Summit Dispatch calling regarding HIGH FIT LOGISTICS LLC (USDOT #1000001). Am I speaking with the person who handles dispatch and freight operations for your fleet? We provide dispatch support and load booking assistance for small carriers. Can you confirm if you currently have active interstate MC operating authority and open capacity on your fleet of 8 trucks? Also, if you're not interested in dispatch assistance, just let me know and I will remove you from our call list immediately."*

### When `config.compliance.sender_identity = ""` (Unset):
- `call_script`: `None`
- `script_status`: `"hidden: sender_identity not set"`
- Frontend UI: The call script box is hidden, preventing cold-calling before operator identity is configured.

---

## 4. Automated Test Verification
Verified by unit tests in [`backend/tests/unit/test_call_queue.py`](../../backend/tests/unit/test_call_queue.py):
- `test_m6_verify_and_call_queue_endpoint`:
  - Verified script generation with configured `sender_identity`.
  - Asserted absence of `"immediate freight volume"`.
  - Asserted presence of opt-out offering and dispatch assistance text.
  - Asserted script hiding (`call_script is None`) when `sender_identity` is empty string.
- All tests pass (3 passed in 2.23s).
