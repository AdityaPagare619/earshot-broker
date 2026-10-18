# EARSHOT — source audit

**Access date: 18 October 2026 (Asia/Kolkata).** This is an evidence ledger, not a claim that every linked site is reliable. All URLs below were opened with the web-page tool or, for repositories, cloned and inspected. Long pages were read in relevant chunks; only the competition rules and Alexa MCP QuickStart were read through all chunks. A successfully retrieved page is not independent verification of every statement it contains. No competitor originality guarantee is justified by this research.

## A. Competition — authoritative for this submission

| ID | Opened source | Finding / consequence |
|---|---|---|
| S01 | [Event](https://amazonappdev2026.devpost.com/) | Self-hosted MCP 2025-11-25+ / Streamable HTTP and simulation paths. Four criteria. Alexa prizes $25k/$15k/$4k. Under-three-minute video. |
| S02 | [Official rules](https://amazonappdev2026.devpost.com/rules) | Read all six chunks. Deadline October 23, 2026, noon Pacific = October 24, 00:30 IST. GitHub public with OSS license OR private shared with reviewers. Rules explicitly also allow a simulation-only alternate path; this design deliberately chooses a real MCP implementation. Equally weighted implementation, design, impact, idea. Up to 10% friction-log bonus. Rules prevail over inconsistent other materials. |
| S03 | [Dates](https://amazonappdev2026.devpost.com/details/dates) | Shows judging starting October 26; rules and FAQ say November 9. Record discrepancy; do not silently merge dates. Submission deadline agrees. |
| S04 | [Resources](https://amazonappdev2026.devpost.com/resources) | Read both chunks. Simulation allowed; credit codes exhausted October 7. Mini-challenge resources. |
| S05 | [Gallery](https://amazonappdev2026.devpost.com/project-gallery) | Gallery not published when accessed. Cannot verify the attachment’s eight-competitor survey from this gallery. |
| S06 | [FAQ](https://amazonappdev2026.devpost.com/details/faqs) | Participants cannot gain gated Alexa+ tooling/device integration access. Own web front end is permitted; explicitly describes a real MCP web client. Local runnable repo and video suffice; continuously hosted service not necessary. |

**Mini-challenge correction:** Rules S02 explicitly name **Kiro Crew**, qualifying on its own as a development tool; do not broaden this to any incidental mention of Kiro. A documented real integration/use is necessary. Open Source asks for a new **additional** project or contribution alongside the primary submission; merely making EARSHOT public should not be assumed sufficient. No submission, external contribution, or mini-challenge qualification was performed in this research.

## B. Alexa+ — documented capability versus unavailable integration

| ID | Opened source | Finding / consequence |
|---|---|---|
| S07 | [Add-ons home](https://developer.amazon.com/docs/alexaplus/add-ons/home) | Select partners only. Both integration paths documented. |
| S08 | [MCP overview](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-toolkit-overview) | Alexa acts as MCP client. States support for 2025-11-25 and MCP Apps. Toolkit availability stated as US. This is not proof of Indian third-party add-on availability. |
| S09 | [QuickStart](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-toolkit-quickstart) | Read all three chunks. Streamable HTTP, remote URL, query round-trip under 500 ms. OAuth code+PKCE S256, canonical resource, PRM; no DCR/CIMD/OIDC/step-up yet. Explicitly says unauthenticated 401 without WWW-Authenticate. Tool changes require redeployment. Security/data policies deferred to a future revision. |
| S10 | [Client lifecycle](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-toolkit-client-lifecycle) | Historical interaction context retained. Elicitation described, but sample initialize uses 2025-03-26 and only roots capability. Example is inconsistent with newer overview; pin target and test negotiation rather than copy it. No demonstrated memory-erasure or speaker-interrupt API here. |
| S11 | [Design guide](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-addon-design-guide) | Explicit: cannot script what Alexa says; design the returned data. |
| S12 | [Layout/rendering](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-addon-layout-and-rendering) | Widget hostContext includes deviceClass, isMobile, displayMode, etc. This is UI surface context, not a signed audience identity supplied to the server. Shared display remains a disclosure channel. |
| S13 | [Certification](https://developer.amazon.com/docs/alexaplus/add-ons/certification-guidelines) | Full workflow, no redirects needed to finish action, no dead ends/silent failures. Privacy-driven phone-only workflows therefore need certification discussion, not a claim of guaranteed approval. |
| S14 | [Functional requirements](https://developer.amazon.com/docs/alexaplus/add-ons/functional-requirements) | Error recovery, continuity, accurate metadata, device adaptation. Clearing an add-on’s own state does not establish power to delete Alexa’s entire history. |
| S15 | [Supported capabilities](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-toolkit-supported-capabilities) | Authentication/account-linking references; does not supply sensing or audio-control APIs. |
| S16 | [Authentication](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-toolkit-authentication) | Two tiers: service client_credentials and user code+PKCE. Normative scope separation says service tokens cannot access user data. One runtime table is inconsistent about scopes; implement restrictive rule and ask for clarification. |
| S17 | [Supplied builder tools URL](https://developer.amazon.com/docs/alexa/devices-builder-tools/home) | Returned 404. |
| S18 | [Resources-linked builder tools URL](https://developer.amazon.com/docs/vega/0.24/mcp-server) → [current guide](https://developer.amazon.com/docs/adbt/get-started) | Successful redirect. Coding-assistant metadata/workflows, full Vega and limited Fire OS support. Not an Echo sensor access API. |
| S19 | [Developer docs directory](https://developer.amazon.com/docs/) | Opened index; navigation only. |
| S20 | [Developer community](https://community.amazondeveloper.com/) | Opened index; not evidence that any EARSHOT-specific capability is supported. |
| S21 | [July builder announcement](https://developer.amazon.com/alexaplus/blogs/2026/07/alexa-plus-new-ways-to-build-experiences) | July 23, 2026; MCP integration and preview paths described. No blanket middleware interception promise. |
| S22 | [India launch](https://www.aboutamazon.in/news/devices-and-alexa/alexa-plus-launch-india) | September 16, 2026 Early Access; English/Hindi/Hinglish and context continuity described. Consumer availability does not imply toolkit access. |
| S23 | [India product page](https://www.amazon.in/Amazon-Alexa/dp/B0H7CM5J66) | Alexa+ Early Access product listing retrieved. Consumer availability only. |

## C. MCP and implementation evidence

| ID | Opened source | Finding / consequence |
|---|---|---|
| S24 | [2025-11-25 specification](https://modelcontextprotocol.io/specification/2025-11-25) | Required design baseline; MCP itself does not enforce all security principles. |
| S25 | [Spec index](https://modelcontextprotocol.io/specification) | Redirected to **2026-07-28**, a newer revision with materially different lifecycle. Do not accidentally adopt it for Alexa baseline. |
| S26 | [2025 transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | Read all chunks. POST/GET, JSON or SSE responses, Origin validation, version headers, session handling, replay isolation. Streamable HTTP is NOT an audio stream. |
| S27 | [MCP Apps overview](https://modelcontextprotocol.io/extensions/apps/overview) | Tool/resource UI + sandboxed host bridge. Sandboxing protects host from app; it does not make the screen private from bystanders. |
| S28 | [Apps API](https://apps.extensions.modelcontextprotocol.io/api/) | Extension, host support varies. Skills help build apps. No mandatory core capability inferred. |
| S29 | [Supplied Agent Skills URL](https://apps.extensions.modelcontextprotocol.io/) | Redirects to Apps API documentation. Not a distinct runtime identity or privacy primitive. |
| S30 | [Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) | PRM discovery via header OR well-known URI in retrieved revision. Alexa’s no-WWW-Authenticate profile can use well-known discovery; do not call that a contradiction automatically. |
| S31 | [Elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation) | Form and URL modes; negotiate actual supported mode. Form must not request credentials. Elicitation is not proof of the speaker’s identity or owner authorization. |
| S32 | [Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Cloned; README, transport security tests and v1.30.0 version declaration inspected. Latest installed initially was 2.3.0; deliberately installed 1.30.0 for 2025-11-25. |
| S33 | [TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) | Cloned README: main is v2 targeting 2026-07-28; v1.x separate. Do not copy main blindly. |
| S34 | [Inspector](https://github.com/modelcontextprotocol/inspector) | Cloned README, CLI smoke guide. Initial 2.5.0 npm install failed. Working test used Inspector launcher 0.21.0 with resolved 0.21.2 subpackages; rerun on Node 22.20.0 succeeded. This is a smoke test, not certification/conformance. |
| S35 | [Strands SDK](https://github.com/strands-agents/sdk-python) | Cloned current repository and inspected README; current tree is a broader harness monorepo. Not used at runtime here. Pin an actual release before implementation. |

Cloned HEAD commits:

- Python: `2af9e3089ac66b35c1550c500aae86a82efb1e17`
- TypeScript: `9bc40e903fde15534ec06ff4c1347d47000dbe16`
- Inspector: `074b8108f340590268f2900741403755e923a11c`
- Strands: `26700e62d0e98b0976c095fc173561fb591f98c3`

See `evidence/` for actual test output. Selected repo reading notes are preserved; full clones are not included in the downloadable pack.

## D. Mini-challenges and visual references

| ID | Opened source | Finding / consequence |
|---|---|---|
| S36 | [AWS Builder](https://builder.aws.com/) | Hub opened. No claim that free tier covers every proposed component. |
| S37 | [Kiro](https://kiro.dev/) | Product page opened; competition eligibility derives from S02, not marketing. |
| S38 | [Hacktoberfest](https://hacktoberfest.com/) | 2026 page explicitly says PRs no longer count toward rewards; different participation system. Separate from Amazon’s Open Source rules. |
| S39 | [Dribbble](https://dribbble.com/) | Browsed design index. No layouts/assets copied. |
| S40 | [Awwwards](https://www.awwwards.com/) | Browsed design index. Consumer experience should not be a dense security-operations dashboard. |

## E. Problem evidence — qualify the failure class

| ID | Opened source | Assessment |
|---|---|---|
| S41 | [WCMU/NPR 2018 recording](https://www.wcmu.org/national-world-news/2018-05-25/amazon-echo-recorded-and-sent-couples-conversation-all-without-their-knowledge) | Reports recording sent to **a contact / husband’s employee**, not simply a stranger. Supports accidental recording/routing risk; NOT a failure EARSHOT’s calendar output gateway could have intercepted. |
| S42 | [PhoneArena Instax](https://www.phonearena.com/news/Alexa-is-the-new-Grinch-assistant-reveals-a-10-year-olds-holiday-present_id120811) | Published **November 30, 2019**, not December. Reports Instax gift announcement with child present, citing The Sun. Relevant secondary anecdote, not prevalence measurement. |
| S43 | [KnowTechie gift guide](https://knowtechie.com/dont-let-alexa-ruin-your-carefully-planned-holiday-surprise/) | Fetch failed twice with HTTP 500. Do not claim to have read it; “every single year” recurrence not established by this link. |
| S44 | [Amazon household forum](https://uk.amazonforum.com/s/question/0D56Q00008B5u7SSAR/how-do-i-stop-announcements-for-my-daughter-and-i-get-hers) | Thread retrieved despite component error. October 2021 complaint and staff response; user disputes Household diagnosis. Historical support evidence, not authoritative current product behavior. |
| S45 | [AEANET orders guide](https://www.aeanet.org/how-do-i-stop-alexa-from-showing-amazon-orders/) | Says disabling shipping/delivery notifications does not stop purchase confirmation. Does **not** prove that no purchase-confirmation suppression mechanism exists anywhere. Low-authority secondary guide. |
| S46 | [On3 spreadsheet thread](https://www.on3.com/boards/threads/alexa-is-listening-and-everything-else-tips-discussion.8958847/) | September 2, 2026 anecdotal privacy settings discussion. Not a controlled study, nor validation of every participant claim. |
| S47 | [ScienceAQ survey reprint](https://www.scienceaq.com/Article/Electronics/72379.html) | Body credits ©2019 USA Today / Tribune. Historical parent survey; do not portray as fresh 2026 research or current population estimates. |
| S48 | [Hindustan Times allegation](https://www.hindustantimes.com/trending/us/mom-accuses-amazon-s-alexa-of-asking-her-4-year-old-daughter-what-she-was-wearing-101773286673066.html) | March 12, 2026. Includes parent allegation AND Amazon explanation: Show and Tell feature misfire, camera prevented from launching, denial of employee intervention. Content/routing issue, not evidence for this disclosure mechanism. |
| S49 | [AI Incident Database report 1036](https://incidentdatabase.ai/reports/1036/) | **Report** 1036 links to **incident 55**, covering a 2017 song misrecognition. Not incident #1036. Out of EARSHOT’s private-data disclosure scope. |
| S50 | [Consumer Reports](https://www.consumerreports.org/electronics/digital-assistants/amazon-alexa-plus-ai-assistant-review-a1667486499/) | December 19, 2025 review; useful calendar capability, agentic/address errors, inconsistent memory. Reviewer experience, not controlled security evaluation. |
| S51 | [The Verge](https://www.theverge.com/tech/1007565/amazon-alexa-plus-review-one-year-echo-show-dot-max) | October 8, 2026 review; smart-home improvements but task completion/memory problems. Supports need to show useful completed work, not just protection. |
| S52 | [iClarified HomeView](https://www.iclarified.com/102816/apple-homeview-vs-echo-show-which-smart-display-faceTime-messages-apple-home) | Redirected to comparison article. Face/account scoping reported; **not** evidence that all listeners are identified or broadcast disclosure solved. No Apple primary-source verification performed; not used as a core argument. |
| S53 | [AnyList firsthand support article](https://help.anylist.com/articles/alexa-issue-early-2026/) | Reports invocation misrouting; developers only receive commands after Alexa routes them. Strong reason not to call EARSHOT universal middleware. |

The hidden-drone dinner reminder in IDEA.md has no independently verified source in the provided attachments or opened evidence. Exclude from factual pitch unless separately sourced.

## F. Additional research opened during this task

| ID | Opened source | Used for |
|---|---|---|
| S54 | [Contextual integrity research, 2024](https://arxiv.org/html/2408.02373v1) | Abstract, motivation, architecture section read. Purpose, subject, recipient and context matter; topic-only ladders incomplete. Do not equate societal norms with automatic user consent. |
| S55 | [FlowSeal preprint, September 2026](https://arxiv.org/html/2609.14003) | Abstract/introduction and attack section read. Deterministic IFC is prior art; omission and cross-channel actions can disclose. Results are authors’ reported results, not reproduced here. |
| S56 | [Dual-LLM pattern](https://simonwillison.net/2023/Apr/25/dual-llm-pattern/) | First two chunks read. Opaque references and separated controller/data flow are prior art, with explicitly acknowledged limits. |
| S57 | [CaMeL, Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) | Abstract and metadata read. Capability-enforced information flows are prior art. No full-paper replication claimed. |
| S58 | [Home Assistant Assist](https://www.home-assistant.io/voice_control/) | Official local voice architecture and personal handset possibility. Local processing is not, by itself, bystander-output privacy. |
| S59 | [Google Calendar freeBusy](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query) | Structured busy intervals and scopes. Data minimization option; busy time itself still discloses schedule information. |
| S60 | [Google Calendar event patch](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch) | Update/notification behavior. Some emails may still be sent with deprecated notification flag false; do not treat calendar mutation as invisible. |

## G. Attached documents

- `FAV.txt`: read in full. Prior recommendation and assertions, not verified runtime evidence.
- `JUDGE_CROSS_EXAMINATION.pdf`: all three pages extracted and read. Appears to be a team-authored anticipated cross-examination, not an authenticated official score sheet. Its objections are useful; its answers are not evidence.
- Its 0.006 ms p99, 8,918 decisions, confidence cutoff 0.6 and zero residual leaks were **not reproduced**. No source code/dataset for those results was supplied. Do not reuse them as our measurements.
