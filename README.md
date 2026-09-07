# 🏥 Enterprise Sales Intelligence & Competitive Benchmarking Platform

An enterprise sales intelligence platform built for medical and dental sales teams. Powered by the **5-Layer Intelligence Stack**, **Scientific Ground-Truth Benchmarks**, **Explainable Point Attribution**, and **Hyper-Local Competitor Context**.

---

## ⚡ 5-Layer Intelligence Stack & Provenance Architecture

```
Layer 1: Empirical Evidence  ──► DOM elements, Script SDKs, HTTP headers, Network endpoints
           │
           ▼
Layer 2: Defensible Findings ──► Deterministic confidence formula (e.g. 97%) with agreement bonus
           │
           ▼
Layer 3: Business Insights   ──► Executive realities (Manual Intake Bottleneck, Blind Ad Spend, Brand Asymmetry)
           │
           ▼
Layer 4: Decision Engine     ──► Deal Triage & Tiering: TIER 1 (Call Today) ──► TIER 4 (Skip)
           │                     Exact Point Attribution: +20 High Reviews, +18 No Booking, +14 Paid Ads
           ▼
Layer 5: SDR Campaigns       ──► Cryptographically Traced Outreach (Day 1 Email, Day 3 LinkedIn, Day 5 SMS, Day 7 Call Script)
```

---

## 🚀 Quickstart & Commands

### 1. Scientific Accuracy Platform Benchmark
Run the ground-truth benchmark suite to verify Precision, Recall, F1, and Confidence Calibration:
```powershell
.venv\Scripts\python.exe main.py benchmark
```

### 2. Live Deal Triage & Point Attribution Ledger
Triage a prospect with exact arithmetic point attribution and executive business insights:
```powershell
.venv\Scripts\python.exe main.py prioritize --url "https://austindentalcare.com" --name "Austin Dental Care" --reviews 120 --rating 4.9
```

### 3. End-to-End Decision Trace & Provenance Audit
Verify that every outbound claim in sales emails is backed by a verifiable chain (`Claim ➔ Insight ➔ Finding ➔ Evidence`):
```powershell
.venv\Scripts\python.exe main.py trace --url "https://austindentalcare.com" --name "Austin Dental Care" --reviews 120
```

### 4. Hyper-Local Competitor Cohort Intelligence
Analyze peer adoption rates across competitors (e.g. *"78% of local clinics in Austin offer online booking; you don't"*):
```powershell
.venv\Scripts\python.exe main.py cohort --query "Dentists in Austin, TX" --limit 10
```

### 5. Run Full Enterprise Pipeline (with Competitor Intelligence)
Search for clinics, fingerprint tech, compute cohort benchmarks, generate PDF reports, and persist to SQLite:
```powershell
.venv\Scripts\python.exe main.py run --query "Dentists in Austin, TX" --limit 20 --reports
```

### 6. Deep Tech Stack Fingerprint (Declarative YAML Rules)
Fingerprint CMS, GA4, GTM, Meta Pixel, CRMs, Cloud, Chatbots, and Booking engines via 40+ rules:
```powershell
.venv\Scripts\python.exe main.py tech --url "https://austindentalcare.com"
```

### 7. Inspect Defensible Evidence Graph (Layer 1 & 2)
```powershell
.venv\Scripts\python.exe main.py findings --url "https://austindentalcare.com" --name "Austin Dental Care"
```

### 8. Generate 4-Touch AI SDR Omnichannel Sequence & Battlecards (Layer 5)
```powershell
.venv\Scripts\python.exe main.py sequence --url "https://austindentalcare.com" --name "Austin Dental Care" --reviews 120 --rating 4.9
```

### 9. Generate 1-Page Executive PDF Digital Maturity Report
```powershell
.venv\Scripts\python.exe main.py report --url "https://austindentalcare.com" --name "Austin Dental Care" --reviews 120 --rating 4.9
```

### 10. Turnkey Client Proposal Generator (3-Tier Packages)
Generate a high-converting, professional HTML client proposal with pricing, ROI model, and deliverables:
```powershell
.venv\Scripts\python.exe main.py proposal --url "https://austinfamilydental.com" --name "Austin Family Dental"
```

### 11. Closed-Loop Sales Outcome Attribution Engine
Inspect empirical win rates, meeting rates, average deal size, and total closed revenue tied to specific findings:
```powershell
.venv\Scripts\python.exe main.py outcomes
```

### 12. Institutional Detector Registry & Versioning
View detector versions, engineering maintainers, changelog, and benchmark coverage:
```powershell
.venv\Scripts\python.exe main.py detectors
.venv\Scripts\python.exe main.py detectors --detail detector.booking
```

### 13. Scale Ground-Truth Benchmark Fixtures
Snapshot any live clinic website into an offline benchmark fixture with auto-generated ground-truth schema:
```powershell
.venv\Scripts\python.exe main.py benchmark-add --url "https://example-dental.com" --name "Example Dental"
```

### 14. SQLite System of Record
```powershell
.venv\Scripts\python.exe main.py db list
.venv\Scripts\python.exe main.py db changes --name "Austin Dental Care"
```

### 15. Single Source of Truth CRM & Kanban Pipeline
Manage 8 stages (`FOUND ➔ AUDITED ➔ EMAIL_PREPARED ➔ SENT ➔ OPENED ➔ REPLIED ➔ MEETING ➔ WON`), timestamped stage transitions, and sales notes:
```powershell
.venv\Scripts\python.exe main.py crm summary
.venv\Scripts\python.exe main.py crm list --stage FOUND
.venv\Scripts\python.exe main.py crm move --lead-id <lead_id> --stage AUDITED --notes "Reviewed practice profile"
.venv\Scripts\python.exe main.py crm note --lead-id <lead_id> --text "Dr. Smith prefers text outreach"
.venv\Scripts\python.exe main.py crm lead --lead-id <lead_id>
```

### 16. Human-in-the-Loop Outreach Review Queue
Inspect pre-drafted emails, subject lines, and PDF attachments before one-click approval and dispatch:
```powershell
.venv\Scripts\python.exe main.py queue list
.venv\Scripts\python.exe main.py queue review --id <queue_id>
.venv\Scripts\python.exe main.py queue approve --id <queue_id> --notes "Approved for morning send"
.venv\Scripts\python.exe main.py queue reject --id <queue_id> --reason "Wrong decision maker"
.venv\Scripts\python.exe main.py queue send-approved
```

### 17. Autonomous Multi-City Morning Scheduler & Incremental Auditing
Automatically discover leads in major markets, skip unchanged websites via SHA256 content hashing to save compute/AI costs, and stage top prospects:
```powershell
.venv\Scripts\python.exe main.py schedule cities
.venv\Scripts\python.exe main.py schedule run-now --limit 5
```

---

## 🧪 Automated Test Suite (30/30 Passed)

Run the test suite across all engines, registries, outcome calculations, CRM pipelines, and schedulers:
```powershell
.venv\Scripts\pytest.exe -v
```

```text
tests/test_cohort.py::test_market_cohort_analyzer PASSED                 [  3%]
tests/test_confidence.py::test_confidence_empty_evidence PASSED          [  6%]
tests/test_confidence.py::test_single_detector_script_evidence PASSED    [ 10%]
tests/test_confidence.py::test_multi_detector_agreement_bonus PASSED     [ 13%]
tests/test_confidence.py::test_three_detector_agreement_bonus PASSED     [ 16%]
tests/test_confidence.py::test_confidence_capped_at_99 PASSED            [ 20%]
tests/test_crm.py::test_crm_stage_validation PASSED                      [ 23%]
tests/test_crm.py::test_crm_database_lifecycle PASSED                    [ 26%]
tests/test_evaluator.py::test_metric_score_calculations PASSED           [ 30%]
tests/test_evaluator.py::test_benchmark_evaluator_against_ground_truth PASSED [ 33%]
tests/test_evidence_graph.py::test_polymorphic_evidence_creation PASSED  [ 36%]
tests/test_evidence_graph.py::test_evidence_graph_lifecycle PASSED       [ 40%]
tests/test_incremental.py::test_compute_content_hash_normalization PASSED [ 43%]
tests/test_incremental.py::test_incremental_auditing_cache[asyncio] PASSED [ 46%]
tests/test_insights.py::test_manual_intake_bottleneck_insight PASSED     [ 50%]
tests/test_insights.py::test_blind_ad_spend_insight PASSED               [ 53%]
tests/test_insights.py::test_reputation_asymmetry_insight PASSED         [ 56%]
tests/test_insights.py::test_optimized_foundation_fallback PASSED        [ 60%]
tests/test_outcomes.py::test_outcome_metric_properties PASSED            [ 63%]
tests/test_outcomes.py::test_outcome_attribution_engine_computation PASSED [ 66%]
tests/test_prioritizer.py::test_tier_1_call_today_assignment PASSED      [ 70%]
tests/test_prioritizer.py::test_tier_4_skip_assignment PASSED            [ 73%]
tests/test_proposals.py::test_proposal_generation PASSED                 [ 76%]
tests/test_queue.py::test_queue_staging_and_lifecycle PASSED             [ 80%]
tests/test_registry.py::test_detector_registry_list PASSED               [ 83%]
tests/test_registry.py::test_detector_registry_metadata PASSED           [ 86%]
tests/test_repositories.py::test_sqlite_lead_repository PASSED           [ 90%]
tests/test_repositories.py::test_sqlite_finding_and_insight_repository PASSED [ 93%]
tests/test_scheduler.py::test_scheduler_morning_cycle[asyncio] PASSED    [ 96%]
tests/test_traceability.py::test_traceability_engine_provenance PASSED   [100%]

============================= 30 passed in 13.32s =============================
```

---

## 🎯 Ground-Truth Benchmark Matrix

Evaluated against 5 diverse, annotated dental practices (`benchmark/dentists/`):

| Detection Signal | Precision | Recall | F1 Score | Accuracy |
|---|:---:|:---:|:---:|:---:|
| **Online Booking** | 100% | 100% | 1.00 | 100% |
| **AI Chatbot** | 100% | 100% | 1.00 | 100% |
| **CMS Detection** | 100% | 100% | 1.00 | 100% |
| **GA4 Analytics** | 100% | 100% | 1.00 | 100% |
| **Ad Pixels** | 100% | 100% | 1.00 | 100% |
| **SSL Status** | 100% | 100% | 1.00 | 100% |
| **Overall Accuracy** | **100.0%** | **100.0%** | **1.00** | **100.0%** |

---

## 📁 Output Formats

Results and deliverables are exported to `output/`:
- `output/proposals/*.html`: Turnkey client proposals with interactive 3-tier pricing, ROI breakdown, and deliverables.
- `leads_enterprise_YYYYMMDD_HHMMSS.csv`: Clean CRM export with Priority Tiers, Attributions, and Key Strategic Insights.
- `leads_enterprise_YYYYMMDD_HHMMSS.json`: Full nested models containing raw evidence, findings, insights, deal priority, decision traces, and SDR sequences.
- `output/reports/*.pdf`: Standalone 1-page executive audit PDFs.
