# TRUCKLEAD AUTOPILOT — Screen Demo Checklist & Playbook

## 1. Demo Recording Artifacts
- **Primary Video Recording**: [`docs/demo/dashboard_demo.webm`](./dashboard_demo.webm)
- **Synchronized Subtitles**: [`docs/demo/dashboard_demo.srt`](./dashboard_demo.srt)
- **PII Audit Evidence**: [`docs/reports/evidence/r7.txt`](../reports/evidence/r7.txt)

---

## 2. Privacy & Compliance Guarantees
1. **DEMO_MODE Enforced**: The recorder strictly blocks execution unless `DEMO_MODE=true` is set.
2. **Real-Time PII Masking**:
   - Phone numbers masked to `(***) ***-XXXX`.
   - Email addresses masked to `o***@carrier.com`.
   - Contact names masked to `J*** D***`.
   - Street addresses masked to `1*** Main St`.
   - API tokens and keys masked to `***`.
3. **Contactability Labeling**: Phones are strictly labeled as **"Format-Valid"**, never misleadingly represented as "Verified".
4. **Database Isolation**: The recording executes against an ephemeral copy under `%TEMP%/trucklead_demo_session/demo_trucklead.db`, guaranteeing zero mutations to production data.
5. **No Automated Transmissions**: The outreach interface is 100% manual click-to-call. Automated transmission endpoints do not exist.

---

## 3. Walkthrough Screen Flow & Subtitles
| Screen # | Screen View | Timestamp (SRT) | Caption Content |
| :---: | :--- | :--- | :--- |
| **1** | Dashboard Overview | `00:00:00,000 --> 00:00:05,500` | 1. Dashboard Overview — 498 Verified Carriers, Multistage Funnel & Lead Source Mix |
| **2** | Leads Database | `00:00:05,500 --> 00:00:11,000` | 2. Leads Database — ICP Filters, Status Badges & Score Bands |
| **3** | Lead Detail Modal | `00:00:11,000 --> 00:00:17,000` | 3. Lead Detail View — 10-Point Grounded Checklist, Official SODA Provenance & Contacts |
| **4** | Ready to Contact Queue | `00:00:17,000 --> 00:00:22,500` | 4. Ready to Contact — Format-Valid Calling Queue with Timezone-Aware Calling Windows |
| **5** | SAFER Verification Form | `00:00:22,500 --> 00:00:28,000` | 5. SAFER Verification & Manual Outcome Form — Strictly Human Manual Click-to-Call Workflow |
| **6** | Prioritized Queue (Max 30) | `00:00:28,000 --> 00:00:33,000` | 6. Prioritized Queue (Max 30) — High-Yield Capacity Planner with Follow-Ups First |
| **7** | Reservoir & Source Yield | `00:00:33,000 --> 00:00:38,000` | 7. Reservoir & Source Yield — 1,182 Staged Candidates Across Benchmark Freight States |
| **8** | Compliance & Settings | `00:00:38,000 --> 00:00:43,500` | 8. Compliance & Settings — TCPA Safe Hours, CAN-SPAM Sender Identity & DNC Suppression |
| **9** | Pipeline Runs & Autopilot | `00:00:43,500 --> 00:00:49,500` | 9. Pipeline Runs & Autonomous Autopilot — Continuous FMCSA Change Monitoring & Emergency Kill Switch |

---

## 4. Burning Hardcoded Captions (Optional FFmpeg Step)
If you wish to produce a hardcoded subtitled MP4 video:
```powershell
# 1. Install FFmpeg (Free via Windows Package Manager)
winget install Gyan.FFmpeg

# 2. Burn subtitles into MP4
ffmpeg -i docs/demo/dashboard_demo.webm -vf "subtitles=docs/demo/dashboard_demo.srt:force_style='FontSize=24,PrimaryColour=&HFFFFFF,BackColour=&H80000000,BorderStyle=4'" docs/demo/dashboard_demo_captioned.mp4
```
