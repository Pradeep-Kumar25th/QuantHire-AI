# QuantHire AI — Business Requirements Document (BRD)

**Document type:** Business Requirements Document  
**Product name:** QuantHire AI  
**Client / organization:** Malomatia (AI Hub enterprise hiring initiative)  
**Document status:** Handover baseline — reflects delivered Non-Prod scope (Oct 2026)  
**Primary environment:** Non-Prod — https://quanthire-npd.malomatia.com  
**Technical companion:** [CONSOLIDATED-TECHNICAL-DOCUMENTATION.md](./CONSOLIDATED-TECHNICAL-DOCUMENTATION.md)  

---

## Document control

| Field | Value |
|-------|--------|
| Version | 1.0 (handover) |
| Prepared for | Malomatia — Hazim, engineering team (Shraddha, Farhaan, HR/recruitment users) |
| Source | Product delivery, KT sessions, implemented application behaviour |
| Approval | *[To be signed by Malomatia product owner / sponsor]* |

**Revision history**

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | Oct 2026 | QuantHire delivery team | Initial consolidated BRD for handover |

---

## 1. Executive summary

QuantHire AI is an **AI-native hiring platform** intended to help Malomatia recruitment and HR teams **create job descriptions faster**, ** ingest and structure candidate resumes**, **match candidates to roles with explainable AI**, and **answer questions about the talent pool** via a conversational assistant (QuantChat).

The platform also provides **ATS-style pipeline** screens (applications, interviews, offers, assessments) so recruiters can manage hiring workflows in one place, with **role-based access** aligned to Microsoft Entra ID (Azure AD) for enterprise SSO.

**Business value:**

- Reduce time to produce **enterprise-grade, Malomatia-aligned job descriptions**.  
- Improve **consistency and compliance** of JD structure (15-section enterprise format).  
- Accelerate **shortlisting** with multi-agent matching and visible reasoning.  
- Increase **self-service insight** into candidates and jobs through grounded chat (RAG).  
- Support **AI adoption measurement** via usage logging and analytics views.  

---

## 2. Business objectives

| ID | Objective | Success indicator |
|----|-----------|-------------------|
| BO-1 | Reduce manual effort in JD authoring | Recruiters generate JD drafts from inputs in minutes vs. hours |
| BO-2 | Standardize JD quality and branding | JDs follow Malomatia enterprise template (15 sections) |
| BO-3 | Digitize candidate intake | CV upload → structured profile stored in central database |
| BO-4 | Improve match quality and transparency | Match scores, evidence, swarm/debate rationale visible to recruiters |
| BO-5 | Enable natural-language talent queries | QuantChat answers from indexed job/candidate data with citations/context |
| BO-6 | Operate securely in Malomatia AI Hub | SSO, RBAC, Azure-hosted data and AI services on Non-Prod |
| BO-7 | Prepare for ongoing enhancement | Code and documentation handed to Malomatia engineering for continuity |

---

## 3. Scope

### 3.1 In scope (delivered / Non-Prod baseline)

| Area | In scope |
|------|----------|
| **User authentication** | Basic auth and/or Entra SSO (configuration-dependent on NPD) |
| **Roles** | Admin, Recruiter, Hiring Manager, Interviewer, Viewer, Candidate (RBAC model) |
| **Jobs** | Create, edit, list, enterprise JD preview, Malomatia Word template export |
| **JD generation** | AI workflow with HR input matrix, validation, save to database |
| **Candidates** | Profiles, resume upload, parsing pipeline |
| **Job matching** | Candidate–job matching with streaming agent activity UI |
| **QuantChat** | Recruiter chat over talent data (RAG) |
| **Applications pipeline** | Applications list and detail views |
| **Interviews, offers, assessments** | Module pages and API support (maturity varies by feature) |
| **Analytics / AI adoption** | Dashboard for AI usage tracking |
| **Feedback** | API for recruiter hiring feedback (quality loop) |
| **Non-Prod deployment** | AKS, Azure Postgres, Blob, Azure OpenAI, Document Intelligence |
| **Documentation & KT** | Sessions 1–3, technical docs, local setup guide |

### 3.2 Out of scope (explicit non-goals for this BRD baseline)

| Area | Out of scope / future |
|------|------------------------|
| Production go-live sign-off | Separate production BRD and cutover plan |
| Payroll, HRIS full integration | Unless added in future phases |
| Candidate self-service portal (full) | Partial candidate role; not full external careers site |
| Multi-tenant SaaS for external customers | Single-tenant Malomatia deployment focus |
| Guaranteed legal compliance sign-off | Legal review of JD content remains HR responsibility |
| 24/7 Malomatia ops SLA | Defined by platform team, not this document |
| Mobile-native apps | Web responsive UI only |

### 3.3 Assumptions

- Users have **corporate Microsoft accounts** where Entra SSO is enabled.  
- **Azure AI Hub** provides OpenAI, Document Intelligence, and AKS hosting.  
- Recruiters are trained on **HR matrix inputs** for JD generation.  
- **English** is the primary language for NPD UI and generated content (unless configured otherwise).  

### 3.4 Constraints

- Non-Prod shares **AI Hub landing zone** resources (naming, networking, security policies).  
- Secrets and keys are **not** embedded in application source code.  
- Heavy AI workloads run **in-process** on API pods (scaling limits apply).  

---

## 4. Stakeholders

| Role | Interest |
|------|----------|
| **Malomatia HR / Recruitment** | Daily use — JDs, candidates, matching, chat |
| **Hiring managers** | Review jobs, candidates, match outcomes |
| **AI Hub / Platform (Hazim)** | Hosting, access, security, handover |
| **Engineering (Shraddha, Farhaan)** | Maintain code, local dev, releases |
| **Identity / IT** | Entra app roles (TAMM), TAMM requests |
| **Delivery / vendor (Pradeep team)** | KT, documentation, transition |

---

## 5. User personas and roles

### 5.1 Personas

| Persona | Needs |
|---------|--------|
| **Recruiter** | Create jobs, upload CVs, run matches, use QuantChat, manage pipeline |
| **Hiring manager** | View jobs and candidates, participate in decisions |
| **Admin** | User/role management, settings, oversight |
| **Viewer** | Read-only access for audit or learning |
| **Interviewer** | Interview scheduling / feedback (pipeline module) |

### 5.2 Business roles (Entra app roles)

| Entra app role | Business meaning |
|----------------|------------------|
| **ADMIN** | Full administrative access |
| **RECRUITER** | Primary power user for AI hiring features |
| **HIRING_MANAGER** | Hiring decision participation |
| **INTERVIEWER** | Interview workflow |
| **VIEWER** | Read-only |

**Access provisioning:** Users must be assigned roles on Entra enterprise application **`AIL-QUANTHIRE-NPD`** via organizational process (e.g. TAMM).

---

## 6. Functional requirements

### 6.1 Authentication and session

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-AUTH-1 | User shall authenticate before accessing dashboard features | Must |
| FR-AUTH-2 | System shall support Microsoft Entra SSO where configured | Must |
| FR-AUTH-3 | System shall map Entra app roles to in-application permissions | Must |
| FR-AUTH-4 | System shall issue a session suitable for BFF/API calls (JWT) | Must |

### 6.2 Jobs and job descriptions

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-JOB-1 | Recruiter shall create and edit job records | Must |
| FR-JOB-2 | Recruiter shall generate a job description using AI from job inputs | Must |
| FR-JOB-3 | Generated JD shall follow **enterprise 15-section** Malomatia structure | Must |
| FR-JOB-4 | Recruiter shall supply HR matrix inputs that constrain/enrich generated content | Must |
| FR-JOB-5 | System shall validate/refine JD through an automated workflow before save | Must |
| FR-JOB-6 | Recruiter shall preview and export JD (including Malomatia Word template) | Should |
| FR-JOB-7 | Job data shall persist in central database for matching and chat | Must |

### 6.3 Candidates and resumes

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-CAN-1 | Recruiter shall upload candidate resume files (PDF and supported formats) | Must |
| FR-CAN-2 | System shall validate uploads (type/size) before processing | Must |
| FR-CAN-3 | System shall extract text (including scanned PDFs via Document Intelligence where configured) | Must |
| FR-CAN-4 | System shall produce structured candidate profile fields from resume | Must |
| FR-CAN-5 | Candidate records shall be searchable and linkable to jobs/applications | Must |
| FR-CAN-6 | Resume content shall be indexed for semantic search (vectors) | Must |

### 6.4 Job matching

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-MATCH-1 | Recruiter shall run candidate–job match for selected pair | Must |
| FR-MATCH-2 | System shall produce overall fit score and dimension breakdown | Must |
| FR-MATCH-3 | System shall show **explainability** (evidence, agent reasoning stream) | Must |
| FR-MATCH-4 | System shall mitigate unsupported claims via evidence verification step | Should |
| FR-MATCH-5 | System shall apply bias-audit step in matching pipeline | Should |

### 6.5 QuantChat (AI recruiter chat)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-CHAT-1 | Recruiter shall ask natural-language questions in chat UI | Must |
| FR-CHAT-2 | Answers shall be grounded in indexed job/candidate data where applicable | Must |
| FR-CHAT-3 | System shall route queries by intent (RAG vs general vs comparison, etc.) | Must |
| FR-CHAT-4 | Conversation shall support multi-turn context within session | Should |

### 6.6 Hiring pipeline (ATS-style)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PIPE-1 | User shall view applications linked to jobs/candidates | Must |
| FR-PIPE-2 | User shall access interviews module | Should |
| FR-PIPE-3 | User shall access offers module | Should |
| FR-PIPE-4 | User shall access assessments module | Should |

### 6.7 Analytics and AI adoption

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-AN-1 | System shall log AI feature usage for adoption reporting | Should |
| FR-AN-2 | Authorized users shall view analytics / AI adoption dashboard | Should |

### 6.8 Feedback and quality loop

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-FB-1 | System shall capture recruiter feedback on hiring outcomes via API | Should |
| FR-FB-2 | System shall support analysis of feedback for drift/improvement hints | Could |

### 6.9 Administration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-ADM-1 | Admin shall access settings appropriate to role | Should |
| FR-ADM-2 | System shall support GDPR-related endpoints for data subject processes | Could |

---

## 7. Non-functional requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-1 | **Security** | Secrets stored in secure configuration (K8s secrets / Key Vault), not in Git |
| NFR-2 | **Security** | HTTPS for user access to Non-Prod URL |
| NFR-3 | **Security** | RBAC enforced on API for protected resources |
| NFR-4 | **Performance** | Long AI operations may take minutes; UI shall use async/streaming where implemented |
| NFR-5 | **Availability** | Non-Prod best-effort; no formal SLA in this BRD |
| NFR-6 | **Scalability** | NPD: limited horizontal scale of API due to in-process agents |
| NFR-7 | **Maintainability** | Code in monorepo with Alembic migrations and CI tests |
| NFR-8 | **Observability** | Logging and optional tracing; in-process QuantChat metrics |
| NFR-9 | **Compatibility** | Modern browsers; Node 20 / Python 3.11 for development |
| NFR-10 | **Data residency** | Non-Prod data in Azure region per AI Hub standard (West Europe reference deployment) |

---

## 8. Business rules

| ID | Rule |
|----|------|
| BR-1 | Only authenticated users with appropriate role may create or modify jobs/candidates |
| BR-2 | JD generation must apply HR matrix overlays before treating output as final |
| BR-3 | Match recommendations are **decision support** — recruiters remain accountable for hiring decisions |
| BR-4 | QuantChat answers for HR data should be grounded; users should verify critical decisions |
| BR-5 | Entra role assignment is authoritative for enterprise access provisioning |
| BR-6 | Personal data handling must follow Malomatia privacy and retention policies |

---

## 9. Integrations (business view)

| Integration | Business purpose |
|-------------|------------------|
| **Microsoft Entra ID** | Single sign-on and role assignment |
| **Azure OpenAI** | JD, parsing, matching, chat intelligence |
| **Azure Document Intelligence** | Resume and document text extraction |
| **Azure Blob Storage** | Store uploaded and processed documents |
| **Azure PostgreSQL** | System of record and vector search |
| **Azure Kubernetes Service** | Host web and API for users |

---

## 10. User journeys (summary)

### 10.1 Generate and publish a job description

1. Recruiter logs in.  
2. Opens Jobs → Create / Generate JD.  
3. Enters title, skills, HR matrix fields.  
4. Starts generation → waits for workflow completion.  
5. Reviews enterprise JD preview → saves job.  
6. Optional: export Malomatia Word document.  

### 10.2 Add candidate from resume

1. Recruiter opens Candidates → Upload resume.  
2. System validates file → extracts and parses.  
3. Candidate profile appears with structured fields.  
4. Data becomes available for matching and QuantChat.  

### 10.3 Match candidate to job

1. Recruiter selects job and candidate.  
2. Runs match (stream shows agent progress).  
3. Reviews score, breakdown, evidence, verdict.  
4. Uses outcome for shortlist / interview decision.  

### 10.4 Ask QuantChat

1. Recruiter opens AI Recruiter Chat.  
2. Asks question about candidates or jobs.  
3. Receives grounded answer; continues conversation as needed.  

---

## 11. Acceptance criteria (Non-Prod handover)

Malomatia may consider handover **accepted** when:

| # | Criterion |
|---|-----------|
| AC-1 | NPD URL is reachable by authorized users |
| AC-2 | At least one **RECRUITER** user can log in and access dashboard |
| AC-3 | Recruiter can create a job and trigger JD generation successfully |
| AC-4 | Recruiter can upload a resume and see a candidate profile |
| AC-5 | Recruiter can run a job match and view results |
| AC-6 | Recruiter can send a QuantChat message and receive a response |
| AC-7 | Source code available in agreed repository (Azure DevOps) |
| AC-8 | Consolidated technical documentation and local setup guide delivered |
| AC-9 | Engineering can run L2 local setup following LOCAL-SETUP-GUIDE |
| AC-10 | Entra access process documented (TAMM / AIL-QUANTHIRE-NPD) |

---

## 12. Risks and dependencies

| Risk / dependency | Impact | Mitigation |
|-------------------|--------|------------|
| Users lack Entra app roles | Cannot log in | TAMM / Identity provisioning |
| Azure AI quota or keys unavailable | AI features fail | Platform monitoring; key rotation process |
| Local dev without Azure keys | Cannot test L3 locally | Use NPD for demos; request dev keys |
| In-memory JD tasks | Lost job status on restart | Re-run generation; future queue |
| BRD vs. future features | Expectation gap | Change control for new FR IDs |

---

## 13. Glossary

| Term | Definition |
|------|------------|
| **JD** | Job Description |
| **BFF** | Backend-for-Frontend — Next.js proxy to API |
| **RAG** | Retrieval-Augmented Generation — chat grounded on stored data |
| **NPD** | Non-Production environment |
| **Entra ID** | Microsoft identity platform (Azure AD) |
| **ATS** | Applicant Tracking System |
| **pgvector** | PostgreSQL extension for vector similarity search |
| **AI Hub** | Malomatia Azure AI landing zone program |

---

## 14. Appendices

### Appendix A — Related documents

| Document | Purpose |
|----------|---------|
| [CONSOLIDATED-TECHNICAL-DOCUMENTATION.md](./CONSOLIDATED-TECHNICAL-DOCUMENTATION.md) | Technical architecture and operations |
| [LOCAL-SETUP-GUIDE.md](./LOCAL-SETUP-GUIDE.md) | Developer local environment |
| [KT-MASTER-INDEX.md](./KT-MASTER-INDEX.md) | KT session materials |
| [TECHNICAL-HANDOVER-TO-MALOMATIA.md](./TECHNICAL-HANDOVER-TO-MALOMATIA.md) | Email-ready handover checklist |

### Appendix B — Entra access (business summary)

- **Application name:** AIL-QUANTHIRE-NPD  
- **Typical role for HR users:** RECRUITER  
- **Process:** Organizational access request (TAMM)  

---

**Approval signatures**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Malomatia product owner | | | |
| Malomatia IT / AI Hub | | | |
| Delivery lead | | | |

---

*End of Business Requirements Document*
