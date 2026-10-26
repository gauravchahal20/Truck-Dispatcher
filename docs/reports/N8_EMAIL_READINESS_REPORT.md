# N8: Email Readiness & CAN-SPAM Compliance Gating Audit

## 1. Executive Summary & Regulatory Framework
Under the CAN-SPAM Act (15 U.S.C. § 7704(a)(5)(A)), any commercial electronic mail message must clearly and conspicuously display:
1. **A valid physical postal address** of the sender.
2. **Accurate header and sender identification** (no deceptive or missing from-lines).

In accordance with user directive N8, commercial email outreach across the platform is hard-gated by the compliance service in [`backend/app/api/routes_compliance.py`](../../backend/app/api/routes_compliance.py).
- **Physical Address Gating**: If `config.compliance.postal_address` is empty or unset, all email endpoints return `readiness_status: "blocked: address not set"` and prevent email generation or export.
- **Sender Identity Gating**: If `config.compliance.sender_identity` is empty, outreach is flagged as `readiness_status: "blocked: sender_identity not set"`.
- **Active Outreach State**: Only when both prerequisites are explicitly configured by the operator does the pipeline report `readiness_status: "ready_for_outreach"`.

---

## 2. Census Email Coverage Breakdown Across Stored Pool (312 Carriers)

### Table 2.1: Overall Email Presence
| Category | Carrier Count | Percentage of Total Carriers | Operational Pipeline Impact |
| :--- | :--- | :--- | :--- |
| **Carriers with Declared Email** | **284** | **91.0%** | Eligible for email verification & CAN-SPAM compliant outreach |
| **Carriers without Email (Phone-Only)** | **28** | **9.0%** | Routed strictly to Voice / Verify-and-Call queue |
| **Total Stored Carriers** | **312** | **100.0%** | - |

### Table 2.2: Coverage by Email Tier
| Email Tier | Address Count | % of Emails | Representative Domains / Format | Outreach Safety & Deliverability |
| :--- | :--- | :--- | :--- | :--- |
| **Generic (Free Webmail)** | **211** | **74.3%** | `@gmail.com`, `@yahoo.com`, `@outlook.com`, `@hotmail.com` | High open rate for single-truck owner-operators; requires individual ESP deliverability pacing. |
| **Named / Corporate** | **48** | **16.9%** | `@summittrucking.com`, `@titaniumtransit.com` | Primary business domain; high authority and decision-maker confidence. |
| **Role-Based** | **24** | **8.5%** | `dispatch@`, `safety@`, `office@`, `admin@`, `info@` | Ideal for direct dispatch load availability queries; low spam complaint risk. |
| **Departmental / Other** | **1** | **0.4%** | Shared operations alias | Operational alias. |
| **Total Declared Emails** | **284** | **100.0%** | - | - |

### Table 2.3: Verification Status Breakdown
| Status Code | Count | Percentage | Definition & Next Action |
| :--- | :--- | :--- | :--- |
| **`UNKNOWN` / `UNVERIFIED`** | **265** | 93.3% | Freshly ingested from federal census mirror; queued for MX validation. |
| **`DOMAIN_OK` / `DELIVERABLE`** | **16** | 5.6% | MX records verified active and accepting inbound mail. |
| **`RISKY`** | **3** | 1.1% | Catch-all domain configuration; requires gentle outreach. |

---

## 3. The "Email-Ready" List Endpoint (`/api/compliance/email-ready-leads`)

### Gating Behavior Demonstration:
```json
// GET /api/compliance/email-ready-leads (When postal_address is unset)
{
  "status": "success",
  "readiness_status": "blocked: address not set",
  "is_blocked": true,
  "block_reason": "CAN-SPAM Act requirement: Physical postal street address is not configured in config.compliance.postal_address.",
  "prerequisites": {
    "postal_address_configured": false,
    "sender_identity_configured": true
  },
  "coverage_summary": {
    "total_email_eligible": 284,
    "by_tier": {
      "generic": 211,
      "named": 48,
      "role": 24
    },
    "by_status": {
      "UNKNOWN": 265,
      "DOMAIN_OK": 16,
      "RISKY": 3
    }
  },
  "total": 284,
  "items": [ ... ]
}
```

```json
// GET /api/compliance/email-ready-leads (When postal_address & sender_identity are configured)
{
  "status": "success",
  "readiness_status": "ready_for_outreach",
  "is_blocked": false,
  "block_reason": null,
  "prerequisites": {
    "postal_address_configured": true,
    "sender_identity_configured": true
  },
  "total": 284,
  "items": [ ... ]
}
```

---

## 4. Test Verification
Verified by automated integration test [`backend/tests/unit/test_email_readiness.py`](../../backend/tests/unit/test_email_readiness.py):
- Confirmed blocking when `postal_address` is empty (`"blocked: address not set"`).
- Confirmed blocking when `sender_identity` is empty (`"blocked: sender_identity not set"`).
- Confirmed activation when both prerequisites are configured (`"ready_for_outreach"`).
- Verified coverage aggregation across generic, named, and role tiers (1 passed in 1.66s).
