# SIH PS 26154 — Technical Presentation Content

## Title Header

**Problem Statement ID:** 26154  
**Problem Statement Title:** Gen AI Platform for Automated Content Transformation  
**Organization:** National Technical Research Organisation (NTRO)  
**Category:** Software  
**Theme:** Blockchain & Cybersecurity

**Solution:** UnifiOps — Enterprise AI Platform for Automated Multi-Format Content Transformation and Threat Intelligence Verification

---

## Section 1 — Idea Title and Proposed Solution

### The operational problem

Security operations centres, intelligence organizations, and defence teams must communicate technical findings to audiences with different needs. An incident may require a concise executive update, a structured advisory, technical analysis, public-facing messages, and visual briefings. Re-authoring these formats manually can introduce delay, inconsistency, and copy errors at the point when clear communication matters most.

The often cited four-hour turnaround is a baseline to establish with participating teams, not a measured result of this proposal. The pilot will record current preparation time and compare it with reviewed UnifiOps output.

### The proposed solution

UnifiOps is a single-source-to-multi-deliverable platform. It ingests reports, advisories, research papers, operational briefs, and analyst-provided text; extracts a canonical representation of source facts; and prepares seven output types:

1. Executive summaries.
2. Structured PDF advisories.
3. LinkedIn posts.
4. X/Twitter threads.
5. Dynamic SVG infographics.
6. PowerPoint presentations with speaker notes.
7. Multi-scene MP4 videos with narration.

A shared orchestration layer supplies each renderer with source context and operator-selected constraints. The operator can review and download generated drafts. Publication and operational decisions remain under authorized human control.

### Design principles

- **One reviewed source of truth:** Keep source identifiers and evidence provenance available across generated formats.
- **Constrained generation:** Pass extracted facts and audience-specific instructions to the local model; treat generated prose as a draft.
- **Human approval:** Require a designated reviewer before external publication or operational distribution.
- **Local control:** Run inference and media synthesis inside the organization’s approved environment, with outbound network access disabled or tightly governed.
- **Auditable processing:** Record who initiated a job, its source digest, configuration, model and evidence versions, validation outcomes, and export actions.

### Distinguishing capabilities

**Deterministic fact preservation.** Pattern-based extraction identifies selected indicators such as CVE identifiers, IP addresses, and severity labels. A verifier compares these indicators with output and reports omissions or changes. This check is useful for consistency, but it does not establish that all statements are true and cannot guarantee zero hallucinations. Similarity retrieval can surface related evidence; it is not itself proof.

**Context-aware visual system.** A design service infers topic and severity cues and supplies palettes, layout suggestions, and visual motifs to SVG, presentation, and video renderers. Rendered assets are reviewed for legibility, factual alignment, and suitability for the intended audience.

**On-premise inference option.** A locally hosted Ollama model and local text-to-speech engine can support processing without a hosted LLM API. Data sovereignty depends on a verified deployment boundary, controlled model and dependency distribution, secure storage, and network egress policy; local inference alone does not guarantee it.

---

## Section 2 — Technical Approach and System Architecture

### Proposed enterprise stack

| Layer | Proposed responsibility |
|---|---|
| Modular operator interface | React and TypeScript dashboard for role-aware access, job submission, parameter controls, evidence preview, review queues, and asset downloads |
| API gateway and identity | Authenticate users, authorize actions, validate requests, enforce upload limits, and issue traceable job identifiers |
| FastAPI services | Separate ingestion, orchestration, generation, verification, evidence retrieval, and export interfaces behind versioned APIs |
| Background workers | Run resource-intensive document, model, presentation, and video jobs asynchronously; expose progress, cancellation, retry, and failure state |
| Local AI inference | Ollama model service hosted within the approved network; model/version selection is recorded per job |
| Render and media services | Python document parsing and synthesis using `python-docx`, PDF tooling, `python-pptx`, WeasyPrint, Pillow, MoviePy, and local TTS |
| Relational control store | SQLite for a single-node evaluation; PostgreSQL for a multi-user deployment, holding users, jobs, configuration, approvals, evidence metadata, and audit references |
| Artifact store | Encrypted, access-controlled storage for uploads and generated outputs, with retention and deletion policies |
| Threat evidence service | Versioned local CISA KEV and CERT-In data, optional approved NVD feeds, provenance, retrieval timestamps, and evidence references |
| Audit and integrity service | SHA-256 digests for source and artifacts; append-only audit events, with chained event hashes and protected backups as a production control |

The React/FastAPI/database stack above is the target deployment architecture. It is a proposed production design; this document does not assert that role-based access, approval queues, distributed workers, PostgreSQL, chained audit records, or a React client are already deployed in the current project.

### Logical architecture

```text
+---------------------------+
| React / TypeScript client |
+-------------+-------------+
              | HTTPS, identity, scoped access
              v
+---------------------------+
| API gateway / FastAPI     |
+------+------+-------------+
       |      |       |
       v      v       v
  Ingestion  Job    Evidence and
  service    API    verification APIs
       |      |       |
       +------+-------+----------------+
                     v                v
             Background workers   Local Ollama
              |       |       |    + local TTS
              v       v       v
            Text    Visual   Video
           outputs  assets   renderer
              \      |       /
               +-----+------+
                     v
     Relational metadata + protected artifact store
                     |
                     v
       Approval, export, and chained audit trail
```

### Canonical job record

Each transformation job should use a versioned record containing at least:

- Job ID, requesting identity, timestamps, and lifecycle status.
- Source name, media type, source SHA-256, extraction status, and retention deadline.
- Redaction policy and counts of detected replacements; never store a credential value in audit metadata.
- Canonical facts with source spans or page references, extraction method, and confidence/review status.
- Operator settings: target audience, tone, language, level of detail, communication objective, and content style.
- Model identifier, model digest/version, prompt/template version, renderer version, and evidence-set version.
- Output artifact IDs and hashes, per-output validation results, reviewer decision, and export events.

Canonical facts should preserve provenance. A fact without a source location or supporting evidence should be marked as inferred or unverified rather than silently promoted to a confirmed operational indicator.

### Data and control pipeline

1. **Authenticated intake:** The client obtains a job ID and submits a supported PDF, DOCX, TXT, or pasted-text payload. The API checks authorization, size/type limits, and safe storage rules.
2. **Source preservation and privacy filtering:** The ingestion service hashes the original source, parses text while retaining page or section locations, and applies configurable redaction for email addresses, tokens, and credential patterns. Redaction rules are versioned; the system records what classes were redacted without copying secrets into logs.
3. **Canonical fact extraction:** The extraction stage identifies candidate CVEs, IP addresses, severity labels, dates, affected products, and recommendations. Each candidate is linked to source evidence. Structured output is validated against a versioned schema. The operator can correct or confirm ambiguous facts.
4. **Threat evidence retrieval:** The evidence service queries the approved local data snapshot or approved internal feed. Results carry source name, record identifier, retrieval time, dataset version, and match basis. NVD, CISA KEV, and CERT-In data are distinct sources and must not be represented as interchangeable authority.
5. **Operator constraint binding:** The orchestrator records audience, tone, language, detail level, objective, and style and passes them with canonical facts to each generation task. Policy rules limit unsupported assertions and require citations or source references where applicable.
6. **Parallelizable synthesis:** Independent text and visual tasks may run concurrently through a bounded worker queue. Video rendering is separately scheduled because it consumes more compute. Parallel execution is a target capability; resource limits, ordering, retries, and partial failures must be managed explicitly.
7. **Verification and review:** Deterministic checks compare required source indicators with each output. Evidence checks report supporting, conflicting, and missing references separately. Similarity scores are triage signals, not factual proof. Failed or uncertain checks enter human review and block automatic publication.
8. **Artifact creation and release:** Renderers create PDF, SVG, PPTX, and narrated MP4 artifacts. Each artifact is hashed and associated with the job record. Authorized reviewers approve, reject, or request regeneration. Downloads and publication integrations require authorization and are audited.
9. **Retention and deletion:** Apply organization-approved retention schedules to source files, intermediate text, generated assets, and logs. Provide auditable deletion workflows and protect required security records according to policy.

### Operator controls

- **Target audience:** Executive leadership, technical responders, partner agencies, or public audiences.
- **Tone:** Neutral, technical, advisory, or urgent, within approved communication policy.
- **Language:** Selected output language, with source indicators retained consistently.
- **Level of detail:** Concise, detailed, or executive brief.
- **Communication objective:** Inform, mitigate, or request urgent action.
- **Content style:** Technical, corporate, or simplified.

The control layer stores the selected values with the job and makes them available to the relevant generators. Validation rules prevent a style or audience option from overriding source facts, safety policy, or required approval.

### Security and trust boundaries

- Authenticate identities and enforce least-privilege access for upload, generation, evidence administration, review, and export.
- Validate file types and sizes; isolate parsers and renderers; scan or sandbox untrusted inputs according to the organization’s malware-handling policy.
- Encrypt network traffic and stored artifacts; separate user-facing APIs from the model and evidence networks.
- Restrict model-service egress and use approved, checksummed model artifacts. For air-gapped deployment, stage and verify models, packages, fonts, and media dependencies through an offline supply-chain process.
- Redact before model processing where policy requires it. Treat redaction as risk reduction, not proof that all sensitive data has been removed.
- Keep source content out of routine logs. Store audit events in protected append-only storage; use SHA-256 and event chaining to detect changes, with key and backup controls where required.
- Record evidence provenance and freshness. Retrieval of a CVE record does not independently confirm that the source document describes that CVE correctly.
- Require human authorization before release. Verification status is a review aid, not an approval decision.

---

## Section 3 — Feasibility, Viability, and Risk Mitigation

### Feasibility

The proposed platform builds on open-source components and supports local model inference. It can avoid per-request hosted LLM charges when deployed with local models. It still requires compute capacity, model and package distribution, patch management, storage, audio/encoding support, and operational support. “No internet dependency” applies only after approved models and dependencies are staged and the environment is tested in its intended network mode.

A modular service boundary allows the operator experience, generation modules, evidence sources, and renderers to evolve independently. A single-node SQLite deployment is appropriate for an evaluation; PostgreSQL, controlled workers, high availability, and centralized identity are production choices that require deployment design and testing.

### Risks and mitigations

| Risk | Mitigation and evidence required |
|---|---|
| CPU/GPU contention during inference and media rendering | Bounded asynchronous queues, job priority, worker limits, cancellation, and load tests using representative documents and video durations |
| Hallucinated, omitted, or misattributed indicators | Preserve source spans, lock exact indicators, compare output fields deterministically, retain evidence citations, flag ambiguity, and require analyst review; measure false-pass and false-flag rates |
| Stale or mismatched threat data | Version datasets, record retrieval times and provenance, schedule approved updates, validate feed integrity, and show evidence age to reviewers |
| PII or credential leakage | Apply policy-driven redaction, minimize retention, restrict access, test redaction against a representative corpus, and review logs and model boundaries |
| TTS voice/backend or media encoder unavailable | Preflight local dependencies, expose a clear failed-job state, retain narration script, and provide a reviewed subtitle-only fallback where policy permits |
| Malicious or malformed uploaded files | Enforce upload limits, isolate parsers, scan or sandbox inputs, and test malformed and adversarial documents |
| Audit tampering or unauthorized export | Append-only event storage, hash chaining, protected backups, role separation, alerting, and periodic integrity verification |
| Air-gap assumptions do not match deployment | Document allowed network paths, stage and checksum dependencies, test with egress disabled, and verify no hidden external service calls |

### Verification and acceptance plan

Before an operational pilot, define a representative and approved corpus spanning PDF, DOCX, TXT, advisory, research, and incident-report inputs. Measure:

- Extraction success and source-location accuracy by document type.
- Redaction precision and recall for approved test patterns.
- Exact retention of CVE, IP, severity, date, and product indicators by output type.
- Reviewer-rated factual support, readability, and audience suitability.
- Evidence match quality and evidence freshness visibility.
- End-to-end latency, queue wait, resource use, and failure/recovery behavior at expected load.
- Audit completeness, artifact hash verification, access-control enforcement, and retention/deletion behavior.
- Narration intelligibility and subtitle fallback behavior across supported deployment hosts.

Acceptance thresholds should be agreed with NTRO stakeholders before testing. Report results with corpus characteristics, model/version, hardware, and test conditions. Do not report zero hallucination or a fixed time-saving figure without measured evidence.

---

## Section 4 — High-Impact Benefits and NTRO Value Proposition

### Expected value

- **Faster preparation:** Generate coordinated drafts for several audiences from one reviewed source. Compare the measured workflow against the organization’s existing baseline; a target such as under 30 seconds is not yet an established result and may exclude review and media-render time.
- **Reduced transcription errors:** Carry selected exact indicators through structured facts and run per-output checks before review. This reduces a known class of copy errors but does not eliminate analyst responsibility or all factual errors.
- **Controlled data handling:** Support local inference and an air-gapped operating mode when the complete deployment—including dependencies, model files, evidence updates, storage, and observability—is configured and verified for it.
- **Consistent communication:** Use shared source facts, operator constraints, template versions, and evidence provenance across text and media deliverables.
- **Traceability:** Associate outputs and review decisions with source and artifact hashes, model and evidence versions, and audit events.

### Pilot outcomes

The pilot should establish the true time baseline, assess analyst acceptance, quantify fact-check performance, and test network isolation and audit controls. The proposed 4-hour-to-under-30-second reduction and any percentage reduction in manual effort are hypotheses for measurement, not performance claims. Approval time, queue load, document complexity, and media rendering must be included in the reported end-to-end measure.

---

## Section 5 — Research and Industry References

1. **CISA, Known Exploited Vulnerabilities Catalog.** A maintained source for vulnerabilities known to be exploited; use it as one input to prioritization and retain dataset provenance. [CISA KEV Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
2. **NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.** The revision requested in the project brief; use it as historical incident-handling guidance and check organizational policy for the applicable edition. [NIST SP 800-61 Rev. 2](https://csrc.nist.gov/pubs/sp/800/61/r2/final)
3. **NIST SP 800-61 Rev. 3, Incident Response Recommendations and Considerations for Cybersecurity Risk Management.** Current NIST revision as of this proposal; relevant to integrating incident response with cybersecurity risk management. [NIST SP 800-61 Rev. 3](https://csrc.nist.gov/pubs/sp/800/61/r3/final)
4. **FIRST CVSS v3.1 and v4.0 specifications.** Use CVSS as a severity framework and retain the version and vector. A CVSS score is not, by itself, a complete contextual risk assessment. [CVSS v3.1](https://www.first.org/cvss/v3-1/specification-document) and [CVSS v4.0](https://www.first.org/cvss/v4.0/specification-document)
5. **ISO/IEC 27001:2022.** Reference for an organization-level information security management system and risk-management approach; this platform alone does not establish conformity or certification. [ISO/IEC 27001](https://www.iso.org/standard/27001)
6. **Ollama API documentation.** Reference for local model invocation and structured generation interfaces; model output still requires application-level validation. [Ollama API](https://docs.ollama.com/api)

---

## Closing Statement

**UnifiOps proposes a controlled path from complex source material to audience-specific communication assets. Its enterprise target architecture combines local inference, source-linked facts, threat evidence, deterministic consistency checks, media generation, and human approval. A measured pilot and deployment security assessment are the next steps for establishing performance, privacy boundaries, and operational readiness for NTRO use.**
