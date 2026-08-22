# Tool reference — `mcp_facture_electronique_fr`

This file is generated from the MCP server's tool registry by `scripts/gen_tool_reference.py`. Do not edit it by hand; run the script instead.

**Tools:** 34

## `check_ppf_annuaire_health`

Check the availability of the PPF Annuaire service (GET /healthcheck).
Use before a directory-management session to ensure the service is reachable.

_No parameters._

## `create_directory_line`

Create a directory line (electronic invoice receiving address)
(POST /ligne-annuaire).

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `siren` | string | yes |  | SIREN of the taxable entity creating this receiving address. |
| `matricule_plateforme` | string | yes |  | 4-digit Approved Platform registration number receiving the invoices. |
| `date_debut_effet` | string | yes |  | Effective start date, ISO YYYY-MM-DD (dateDebutEffet). |
| `siret` | string | null | no | `None` | Specific establishment SIRET. If absent, applies to the whole SIREN. |
| `identifiant_routage` | string | null | no | `None` | Routing-code identifier to refine the address. |
| `suffixe_adressage` | string | null | no | `None` | Addressing suffix (suffixeAdressage). |
| `date_fin_effet` | string | null | no | `None` | Effective end date, ISO YYYY-MM-DD, if known. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call. |

## `create_routing_code`

Create a routing code (POST /code-routage).

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `siret` | string | yes |  | Establishment SIRET (14 digits) this routing code belongs to. |
| `identifiant_routage` | string | yes |  | Routing-code identifier to create (max 100 chars, pattern [-_/@a-zA-Z0-9]). |
| `type_identifiant_routage` | string | yes |  | 4-digit type code for the routing-code identifier (typeIdentifiantRoutage). |
| `libelle_code_routage` | string | yes |  | Human-readable label for the routing code. |
| `nature_etablissement` | string | yes |  | Whether the establishment is private or public. |
| `etat_administratif` | string | no | `'A'` | 'A' (active) or 'F' (closed). |
| `gestion_engagement_juridique` | boolean | null | no | `None` | Whether a legal-commitment number (engagement juridique) is mandatory. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call. |

## `create_webhook`

Subscribe to webhook notifications from the Approved Platform.

The AP will POST event payloads to the callback URL whenever a flow
matching the specified filters (flow type, direction, processing rule,
ack status) is created or updated.

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `callback_url` | string | yes |  | URL the Approved Platform will POST notifications to. Must be HTTPS and reachable from the AP network. |
| `flow_type` | string | yes |  | Flow type to subscribe to: CustomerInvoice, SupplierInvoice, CustomerInvoiceLC, SupplierInvoiceLC, AggregatedCustomerTransactionReport, UnitaryCustomerTransactionReport, AggregatedCustomerPaymentReport, UnitaryCustomerPaymentReport, UnitarySupplierTransactionReport, MultiFlowReport, StateInvoice, StateCustomerInvoiceLC, StateSupplierInvoiceLC. |
| `flow_direction` | string | yes |  | Direction filter: 'In' for incoming flows (from PDP to OD), 'Out' for outgoing flows (from OD to PDP). |
| `processing_rule` | string | null | no | `None` | Optional processing rule filter: B2B, B2BInt, B2C, B2G, etc. |
| `ack_status` | string | null | no | `None` | Optional acknowledgement status filter: Pending, Ok, Error. |
| `auth_type` | string | null | no | `None` | Authentication type for the callback: BASIC or OAUTH2. |
| `auth_user_id` | string | null | no | `None` | User ID for BASIC authentication on the callback URL. |
| `auth_user_password` | string | null | no | `None` | Password for BASIC authentication on the callback URL. |
| `auth_token_url` | string | null | no | `None` | Token URL for OAUTH2 authentication on the callback. |
| `auth_client_id` | string | null | no | `None` | Client ID for OAUTH2 authentication on the callback. |
| `auth_client_secret` | string | null | no | `None` | Client secret for OAUTH2 authentication on the callback. |
| `signature_algo` | string | null | no | `None` | Signature algorithm: RS256, HS256, ECDSA, EDDSA_25519, RSA_PSS, EDDSA_448. |
| `signature_key` | string | null | no | `None` | Base64-encoded signing key for webhook payload verification. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call; supply on the second call to execute. |

## `delete_directory_line`

Delete a directory line (DELETE /ligne-annuaire/id-instance:{id-instance}).

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the directory line to delete. WARNING: this action is permanent. After deletion, senders will no longer be able to send invoices via this address. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call. |

## `delete_webhook`

Delete (unsubscribe from) a webhook. After deletion, the AP will
stop sending notifications to the callback URL.

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `webhook_uid` | string | yes |  | UUID of the webhook subscription to delete. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call; supply on the second call to execute. |

## `get_company_by_id_instance`

Look up a legal unit by directory instance ID (GET /siren/id-instance:{id-instance}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the legal unit, from a previous search. |

## `get_company_by_siren`

Look up a legal unit by SIREN (GET /siren/code-insee:{siren}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `siren` | string | yes |  | Exact SIREN (9 digits, no spaces). |

## `get_directory_line`

Look up a directory line by directory instance ID (GET /ligne-annuaire/id-instance:{id-instance}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the directory line. |

## `get_directory_line_by_code`

Look up a directory line by addressing code (GET /ligne-annuaire/code:{identifiant-adressage}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `identifiant_adressage` | string | yes |  | Addressing identifier (identifiantAdressage). |

## `get_establishment_by_id_instance`

Look up an establishment by directory instance ID (GET /siret/id-instance:{id-instance}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the establishment, from a previous search. |

## `get_establishment_by_siret`

Look up an establishment by SIRET (GET /siret/code-insee:{siret}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `siret` | string | yes |  | Exact SIRET (14 digits, no spaces). |

## `get_flow`

Retrieve a flow by its identifier. docType allows choosing between
JSON metadata (Metadata), the original document (Original), the converted
document (Converted), or the readable representation (ReadableView).
By default, returns the JSON metadata (status, dates, identifiers).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `flow_id` | string | yes |  | Flow identifier assigned by the Approved Platform (returned by submit_flow or search_flows, maxLength 36). |
| `doc_type` | string | no | `'Metadata'` | Document type to retrieve: Metadata (default, returns the flow's JSON metadata — recommended), Original (original submitted document, returned as base64), Converted (document converted by the AP, returned as base64), ReadableView (human-readable PDF representation, returned as base64). |

## `get_routing_code_by_id_instance`

Look up a routing code by directory instance ID (GET /code-routage/id-instance:{id-instance}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the routing code. |

## `get_routing_code_by_siret_and_code`

Look up a routing code by SIRET and code (GET /code-routage/siret:{siret}/code:{identifiant-routage}).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `siret` | string | yes |  | Establishment SIRET (14 digits). |
| `identifiant_routage` | string | yes |  | Routing-code identifier (identifiantRoutage). |

## `get_webhook`

Retrieve the full details of a webhook subscription: callback URL,
authentication mode, signature configuration, and metadata filters
(flow type, direction, processing rule, ack status).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `webhook_uid` | string | yes |  | UUID of the webhook subscription to retrieve. |

## `healthcheck_flow`

Check the availability of the Approved Platform's Flow Service.
Returns the operational status of the service (ok/degraded/unavailable).
Use before an invoice submission session to ensure the AP is reachable.

_No parameters._

## `list_webhooks`

List all webhook subscription IDs owned by the current OAuth2 token holder.

Returns a list of webhook UUIDs. Use get_webhook with each ID to retrieve
the full subscription details (callback URL, filters, authentication).

_No parameters._

## `replace_directory_line`

Fully replace a directory line (PUT /ligne-annuaire/id-instance:{id-instance}).

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the directory line. |
| `matricule_plateforme` | string | yes |  | Approved Platform registration number. |
| `date_fin_effet` | string | null | no | `None` | Effective end date, ISO YYYY-MM-DD, if any. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call. |

## `replace_routing_code`

Fully replace a routing code (PUT /code-routage/id-instance:{id-instance}).
Unlike update_routing_code, all fields are required and replace the
existing object entirely.

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the routing code. |
| `type_identifiant_routage` | string | yes |  | 4-digit type code (typeIdentifiantRoutage). |
| `libelle_code_routage` | string | yes |  | Label for the routing code. |
| `etat_administratif` | string | yes |  | 'A' (active) or 'F' (closed). |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call. |

## `search_company`

Search legal units (SIRENs) in the PPF Annuaire (POST /siren/recherche).

A company must appear here before its establishments (SIRETs) or
directory lines (ligne-annuaire) can be resolved. Prefer
get_company_by_siren when the exact SIREN is already known.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `raison_sociale` | string | null | no | `None` | Legal/trade name (partial match). Use when the SIREN is unknown. |
| `siren` | string | null | no | `None` | Exact SIREN (9 digits, no spaces). |
| `type_entite` | string | null | no | `None` | Entity type filter (typeEntite). |
| `etat_administratif` | string | null | no | `None` | Administrative status filter (etatAdministratif). |
| `limite` | integer | no | `50` | Maximum number of results (limite). |
| `ignorer` | integer | no | `0` | Number of results to skip for pagination (ignorer). |

## `search_directory_line`

Search directory lines (electronic invoice receiving addresses)
(POST /ligne-annuaire/recherche).

Call before sending an invoice to verify the recipient has a
registered line and to identify their Approved Platform.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `identifiant_adressage` | string | null | no | `None` | Exact addressing identifier (identifiantAdressage). |
| `matricule_plateforme` | string | null | no | `None` | 4-digit Approved Platform registration number. |
| `siren` | string | null | no | `None` | SIREN (9 digits). |
| `siret` | string | null | no | `None` | SIRET (14 digits). |
| `identifiant_routage` | string | null | no | `None` | Routing-code identifier. |
| `limite` | integer | no | `50` | Maximum number of results (limite). |
| `ignorer` | integer | no | `0` | Number of results to skip for pagination (ignorer). |

## `search_establishment`

Search establishments (SIRETs) in the PPF Annuaire (POST /siret/recherche).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `siret` | string | null | no | `None` | Exact SIRET (14 digits, no spaces). |
| `siren` | string | null | no | `None` | Parent SIREN (9 digits). Lists all establishments. |
| `denomination` | string | null | no | `None` | Establishment name (partial match). |
| `etat_administratif` | string | null | no | `None` | Administrative status filter (etatAdministratif). |
| `limite` | integer | no | `50` | Maximum number of results (limite). |
| `ignorer` | integer | no | `0` | Number of results to skip for pagination (ignorer). |

## `search_flows`

Search flows (invoices, statuses, e-reportings) in the Approved Platform
by criteria: flow type, status, processingRule, period, trackingId.
Pagination via updatedAfter: use the 'nextUpdatedAfter' field from the response
as the updated_after parameter value to get the next page.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `processing_rule` | string | null | no | `None` | Filter by processing rule: B2B, B2BInt, B2C, OutOfScope, ArchiveOnly, NotApplicable. |
| `flow_type` | string | null | no | `None` | Filter by flow type: Invoice, CreditNote, EReportingB2B, EReportingB2C, LifecycleStatus, etc. |
| `status` | string | null | no | `None` | Filter by flow status. Examples: Deposited, Processing, Delivered, Rejected, Approved, Refused. Refer to the AP documentation for the complete list. |
| `updated_after` | string | null | no | `None` | Pagination: only return flows updated after this date/time (ISO 8601 format, e.g. 2024-09-01T00:00:00Z). Use the 'nextUpdatedAfter' value from the previous response to paginate. |
| `tracking_id` | string | null | no | `None` | Filter by trackingId (sender free-form identifier, maxLength 36). |
| `limit` | integer | no | `50` | Maximum number of flows to return (1-500, default 50). |

## `search_routing_code`

Search routing codes (POST /code-routage/recherche).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `identifiant_routage` | string | null | no | `None` | Exact routing-code identifier (identifiantRoutage). |
| `siret` | string | null | no | `None` | Establishment SIRET (14 digits). |
| `libelle_code_routage` | string | null | no | `None` | Routing code label (partial match). |
| `etat_administratif` | string | null | no | `None` | 'A' (active) or 'F' (closed). |
| `limite` | integer | no | `50` | Maximum number of results (limite). |
| `ignorer` | integer | no | `0` | Number of results to skip for pagination (ignorer). |

## `submit_flow`

Submit an electronic invoice, e-reporting, or lifecycle status to the Approved Platform.

Scope: Compatible Solution (CS) mode, no payload validation. See README "Scope" section.

This is the primary action for sending B2B invoices (Factur-X, UBL, CII),
B2BInt/B2C e-reportings, or CDAR lifecycle status messages.

HUMAN-IN-THE-LOOP: This tool requires explicit user confirmation.
Call without confirmation_token first; show the returned summary to the user;
then call again with the provided token to execute the submission.

BEHAVIOR:
- Submission is asynchronous: the AP returns a flowId and an initial status (typically 'Deposited'),
  not the final delivery status. Poll get_flow(flow_id) or search_flows to track processing.
- Returns an error dict (with 'error' key) if the base64 encoding is invalid.
- The AP may reject the flow synchronously (e.g. malformed XML, unknown recipient, quota exceeded);
  in that case the response contains an error code and message.
- If processing_rule is B2B, the recipient must be registered in the PPF directory with an active
  directory line; verify with get_directory_line before submitting.

RESPONSE on success: includes flowId (AP-assigned identifier), trackingId (echoed back),
status (initial processing status), and submittedAt timestamp.

USAGE GUIDELINES:
- Always call get_directory_line (or search_directory_line) first to confirm the recipient is
  reachable and to identify their Approved Platform before submitting a B2B invoice.
- Set a meaningful tracking_id (invoice number or UUID) to simplify later retrieval via search_flows.
- After submission, use get_flow(flow_id, doc_type='Metadata') to monitor the flow status.
- For lifecycle statuses on received invoices (Refused, Approved, etc.), prefer submit_lifecycle_status
  which provides structured status fields and handles mandatory PPF transmissions.
- Call healthcheck_flow before a batch submission to confirm the AP is available.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `file_base64` | string | yes |  | File content encoded in base64. Accepted formats: Factur-X (PDF/A-3 with embedded XML), UBL 2.1 (XML), UN/CEFACT CII D22B (XML). Maximum file size is defined by the Approved Platform (typically a few MB). |
| `file_name` | string | yes |  | File name with extension (e.g. 'invoice_2024_001.xml', 'invoice_2024_001.pdf'). The AP uses the extension to detect the format when flow_syntax is ambiguous. |
| `flow_syntax` | string | yes |  | Syntax/format of the submitted file (required). Common values: FacturX — PDF/A-3 with embedded Factur-X XML; UBL — UBL 2.1 XML invoice or credit note; CII — UN/CEFACT CII D22B XML invoice; CDAR — XML lifecycle status document; EReporting — B2B or B2C e-reporting flow. |
| `processing_rule` | string | yes |  | Processing rule that determines routing and PPF transmission obligations. B2B: domestic invoice between French VAT-registered entities (routed + reported to PPF). B2BInt: international invoice or cross-border e-reporting. B2C: invoice to a non-taxable entity or B2C e-reporting. B2G: invoice to a public-sector entity (v1.2.0). B2GInt: international invoice to a public-sector entity (v1.2.0). B2GOutOfScope: public-sector transaction outside reform scope (v1.2.0). OutOfScope: transaction outside the reform scope (archived only). ArchiveOnly: archiving without routing to recipient. NotApplicable: used for lifecycle status (CDAR) flows. |
| `flow_type` | string | yes |  | Business type of the submitted flow. Common values: Invoice, CreditNote, DebitNote, EReportingB2B, EReportingB2C, LifecycleStatus. Refer to your Approved Platform's documentation for the exhaustive list. |
| `tracking_id` | string | null | no | `None` | Sender-assigned tracking identifier (free-form, maxLength 36). Recommended: use the invoice number or an internal UUID. Allows retrieving this specific flow later via search_flows(tracking_id=...). |
| `confirmation_token` | string | null | no | `None` | Confirmation token returned by a previous call to this tool. Required to actually submit; omit on the first call to receive a summary and token for user approval. |

## `submit_lifecycle_status`

Emit a processing status on a received invoice: Refused, Approved,
PartiallyApproved, Disputed, Suspended, Cashed, PaymentTransmitted,
Cancelled. Refused and Cashed are mandatory transmissions to PPF.
Reason is mandatory for Refused, Disputed, PartiallyApproved, and Suspended.

Builds a real CDAR (CrossDomainAcknowledgementAndResponse, XP Z12-014 v1.4)
document — see mcp_facture_electronique_fr.clients.flow_client for the
MDT-* field mapping this depends on.

HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
first, show the summary to the user, then call again with the token.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `referenced_flow_id` | string | yes |  | Identifier of the invoice flow to which this status applies (flowId returned upon receipt, maxLength 36). Used only for the platform's own flow tracking (flowInfo.trackingId) — not part of the CDAR document content. |
| `status_code` | string | yes |  | Lifecycle status code to emit. Values defined in XP Z12-014 v1.4 (June 2026): Refused (transmitted to PPF), Approved, PartiallyApproved, Disputed, Suspended, Cashed (transmitted to PPF), PaymentTransmitted, Cancelled. Refused and Cashed are mandatory transmissions to PPF. |
| `invoice_id` | string | yes |  | BT-1 invoice number of the referenced invoice (CDAR MDT-87). |
| `invoice_issue_date` | string | yes |  | BT-2 invoice date, ISO 8601 (YYYY-MM-DD) (CDAR MDT-100). |
| `issuer_party_id` | string | yes |  | GlobalID (e.g. SIREN) of the party emitting this status — you or the counterparty, whichever this MCP server acts on behalf of (CDAR MDT-38). |
| `issuer_party_name` | string | yes |  | Name of the emitting party (CDAR MDT-39). |
| `issuer_role_code` | string | yes |  | Role of the emitting party: SE (seller) or BY (buyer) (CDAR MDT-40). |
| `recipient_party_id` | string | yes |  | GlobalID of the counterparty receiving this status (CDAR MDT-57). |
| `recipient_party_name` | string | yes |  | Name of the counterparty (CDAR MDT-58). |
| `recipient_role_code` | string | yes |  | Role of the counterparty — opposite of issuer_role_code (CDAR MDT-59). |
| `party_id_scheme` | string | no | `'0002'` | schemeID attribute shared by both party GlobalIDs (default '0002' = SIRENE, per every bundled AFNOR worked example). |
| `recipient_uri` | string | null | no | `None` | Counterparty's electronic address on the CEF network, if known (CDAR MDT-73). |
| `invoice_type_code` | string | no | `'380'` | BT-3 invoice type code (CDAR MDT-91, default '380' = Invoice). |
| `receipt_datetime` | string | null | no | `None` | Original receipt timestamp of the referenced invoice, ISO 8601 (CDAR MDT-95). Defaults to the current time if omitted — supply the real value when known for an accurate audit trail. |
| `reason` | string | null | no | `None` | Status reason (CDAR MDT-114), mandatory per XP Z12-014 Annex A for Refused, Disputed, PartiallyApproved, and Suspended. Free text. |
| `reason_code` | string | null | no | `None` | Coded reason (CDAR MDT-113) from the per-status motif list in XP Z12-014 Annex A 'Tableau des motifs de STATUTS' (e.g. TX_TVA_ERR, DOUBLON). Not validated against that list. |
| `payment_date` | string | null | no | `None` | Payment date (ISO 8601 format: YYYY-MM-DD). Provided for Cashed and PaymentTransmitted statuses. |
| `payment_amount` | string | null | no | `None` | Payment amount (decimal string, e.g. '1250.00'). Provided for Cashed and PaymentTransmitted statuses. |
| `currency` | string | no | `'EUR'` | ISO 4217 currency code for payment_amount (default EUR). |
| `requested_action_code` | string | null | no | `None` | Coded requested action (CDAR MDT-121), e.g. 'CNF' ('Créer un Avoir total') per the bundled En_litige worked example. Typically used with Disputed. |
| `requested_action` | string | null | no | `None` | Free-text requested action (CDAR MDT-122). |
| `included_note` | string | null | no | `None` | Free-text note (CDAR IncludedNote/Content) per the bundled Rejetee worked example. |
| `confirmation_token` | string | null | no | `None` | Confirmation token from a previous call. Omit on the first call; supply on the second call to execute. |

## `submit_payment_report`

Submit a DGFiP Flux 10.2 / 10.4 payment e-reporting flow.

Scope: Compatible Solution (CS) mode, no payload validation. See README "Scope" section.

Builds a FRR XML payload conforming to DGFiP Spécifications Externes v3.2
(payment.xsd / ereporting.xsd) and submits it to the Approved Platform
via POST /v1/flows with flowSyntax="FRR".

Use for:
  - International B2B payment reporting (processing_rule=B2BInt,
    flow_type=UnitaryCustomerPaymentReport)
  - B2C individual payment reporting (processing_rule=B2C,
    flow_type=UnitaryCustomerPaymentReport)
  - Aggregated B2C payment reporting (processing_rule=B2C,
    flow_type=AggregatedCustomerPaymentReport)

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `transmission_id` | string | yes |  | TT-1: Unique identifier for this transmission (generated by sender). |
| `issue_datetime` | string | yes |  | TT-3: Transmission creation timestamp, e.g. '20250115T120000+0100'. |
| `type_code` | string | yes |  | TT-4: Transmission type code, e.g. '380'. |
| `sender_id` | string | yes |  | TT-8: Identifier of the CS/PDP platform submitting the report. |
| `sender_id_scheme` | string | yes |  | TT-7: ID scheme for sender, e.g. 'SIREN', 'SIRET'. |
| `sender_name` | string | yes |  | TT-9: Legal name of the sender platform. |
| `sender_role_code` | string | yes |  | TT-10: Sender role code: 'CS', 'PDP', 'OD', or 'MOA'. |
| `issuer_id` | string | yes |  | TT-13: SIREN or SIRET of the French declarant. |
| `issuer_id_scheme` | string | yes |  | TT-12: ID scheme for issuer: 'SIREN' or 'SIRET'. |
| `issuer_name` | string | yes |  | TT-14: Legal name of the declarant. |
| `issuer_role_code` | string | yes |  | TT-15: Issuer role: 'MOA' or 'OD'. |
| `period_start` | string | yes |  | TT-89: Report period start date (ISO 8601, e.g. '2025-01-01'). |
| `period_end` | string | yes |  | TT-90: Report period end date (ISO 8601, e.g. '2025-01-31'). |
| `invoices_json` | string | yes |  | JSON array of payment records.  Each invoice in the `invoices` JSON list must have:  Required fields:   invoice_id    TT-91  Invoice number (reference to the original invoice)   issue_date    TT-102 Invoice issue date (ISO 8601)   payment_date  TT-92  Payment date (ISO 8601)   subtotals     TT-93..95  List of payment breakdown objects  subtotals list entries:   tax_percent   TT-93  VAT rate (decimal, e.g. "20.0")   amount        TT-95  Collected amount at this rate (decimal string)   currency_code TT-94  (optional) Currency code (e.g. "EUR") |
| `flow_type` | string | yes |  | XP Z12-013 FlowType for this payment report:   UnitaryCustomerPaymentReport    — Flux 10.2 unit payment   AggregatedCustomerPaymentReport — Flux 10.4 aggregated B2C payment |
| `processing_rule` | string | yes |  | B2BInt for international B2B payments, B2C for B2C payments. |
| `transmission_name` | string | null | no | `None` | TT-2: Optional human-readable name for the transmission. |
| `tracking_id` | string | null | no | `None` | Optional external tracking identifier for this flow. |
| `confirmation_token` | string | null | no | `None` | Confirmation token returned by a prior pending response. |

## `submit_transaction_report`

Submit a DGFiP Flux 10.1 / 10.3 transaction e-reporting flow.

Scope: Compatible Solution (CS) mode, no payload validation. See README "Scope" section.

Builds a FRR XML payload conforming to DGFiP Spécifications Externes v3.2
(transaction.xsd / ereporting.xsd) and submits it to the Approved Platform
via POST /v1/flows with flowSyntax="FRR".

Use for:
  - International B2B outbound sales (processing_rule=B2BInt,
    flow_type=IndividualCustomerTransactionReport)
  - International B2B inbound purchases (processing_rule=B2BInt,
    flow_type=UnitarySupplierTransactionReport)
  - B2C individual transactions (processing_rule=B2C,
    flow_type=IndividualCustomerTransactionReport)
  - Aggregated B2C reports (processing_rule=B2C,
    flow_type=AggregatedCustomerTransactionReport)

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `transmission_id` | string | yes |  | TT-1: Unique identifier for this transmission (generated by sender). |
| `issue_datetime` | string | yes |  | TT-3: Transmission creation timestamp, e.g. '20250115T120000+0100'. |
| `type_code` | string | yes |  | TT-4: Transmission type code, e.g. '380' (invoice report). |
| `sender_id` | string | yes |  | TT-8: Identifier of the CS/PDP platform submitting the report. |
| `sender_id_scheme` | string | yes |  | TT-7: ID scheme for sender, e.g. 'SIREN', 'SIRET', 'TVA', '0088'. |
| `sender_name` | string | yes |  | TT-9: Legal name of the sender platform. |
| `sender_role_code` | string | yes |  | TT-10: Sender role code. Use 'CS' (Compatible Solution), 'PDP', 'OD' (obligataire délégant), or 'MOA' (assujetti). |
| `issuer_id` | string | yes |  | TT-13: SIREN or SIRET of the French taxable entity (déclarant). |
| `issuer_id_scheme` | string | yes |  | TT-12: ID scheme for issuer, typically 'SIREN' or 'SIRET'. |
| `issuer_name` | string | yes |  | TT-14: Legal name of the declarant. |
| `issuer_role_code` | string | yes |  | TT-15: Issuer role code. Use 'MOA' (assujetti / declarant) or 'OD' (obligataire délégant). |
| `period_start` | string | yes |  | TT-17: Report period start date in ISO 8601 format (e.g. '2025-01-01'). |
| `period_end` | string | yes |  | TT-18: Report period end date in ISO 8601 format (e.g. '2025-01-31'). |
| `invoices_json` | string | yes |  | JSON array of invoice transaction records.  Each invoice in the `invoices` JSON list must have:  Required fields:   id                          TT-19  Invoice number / identifier   issue_date                  TT-20  Issue date (ISO 8601, e.g. "2025-01-15")   type_code                   TT-21  Invoice type: "380" (invoice), "381" (credit note), "389" (self-billed)   currency_code               TT-22  ISO 4217 currency code (e.g. "EUR", "USD")   business_process_id         TT-28  Business process ID (e.g. "A1", "A2")   business_process_type_id    TT-29  Process type: "EREP" (e-reporting), "EINV" (e-invoicing)   seller_company_id           TT-33  Seller identifier (SIREN, SIRET, VAT number, etc.)   seller_company_id_scheme    TT-33-1 Scheme: "SIREN", "SIRET", "0088" (GLN), "TVA", etc.   monetary_total_tax_amount   TT-52  Total VAT amount (decimal string, e.g. "200.00")   monetary_total_currency     TT-202 Currency code for the tax amount (e.g. "EUR")   tax_subtotals               TT-54..59  List of VAT breakdown objects (see below)  Optional fields:   due_date                    TT-201 Payment due date (ISO 8601)   tax_due_date_type_code      TT-24  VAT due date code ("3" cash, "4" invoice date, "5" delivery)   tax_exclusive_amount        TT-51  Total amount excluding VAT   seller_tax_registration_id  TT-34  Seller VAT number (e.g. "FR12345678901")   seller_tax_registration_id_qualifier TT-34-0  Qualifier (default "VA")   seller_country              TT-35  ISO 3166-1 alpha-2 country code   buyer_company_id            TT-36  Buyer identifier (for international B2B)   buyer_company_id_scheme     TT-37  Buyer ID scheme   buyer_tax_registration_id   TT-38  Buyer VAT number   buyer_tax_registration_id_qualifier TT-38-0  Qualifier (default "VA")   buyer_country               TT-39  Buyer country code  tax_subtotals list entries:   taxable_amount              TT-54  Tax base amount (decimal string)   tax_amount                  TT-55  VAT amount for this category (decimal string)   tax_percent                 TT-57  VAT rate (decimal, e.g. "20.0", "5.5", "0.0")   code                        TT-56  (optional) VAT category code: "S" standard, "Z" zero, "E" exempt   exemption_reason            TT-58  (optional) Exemption reason text   exemption_reason_code       TT-59  (optional) Exemption reason code — free-form,                                      not enforced by this server; see VATEX_CODES_EU                                      and VATEX_CODES_FR (NF XP Z12-012 Annex A v1.4,                                      June 2026) for the accepted code list |
| `flow_type` | string | yes |  | XP Z12-013 FlowType for this e-reporting submission:   IndividualCustomerTransactionReport — Flux 10.1 individual B2C or intl B2B   AggregatedCustomerTransactionReport — Flux 10.3 aggregated B2C   UnitarySupplierTransactionReport    — Flux 10.1 intl B2B purchases   MultiFlowReport                     — mixed flow types |
| `processing_rule` | string | yes |  | XP Z12-013 ProcessingRule:   B2BInt — international B2B e-reporting   B2C    — B2C e-reporting |
| `transmission_name` | string | null | no | `None` | TT-2: Optional human-readable name for the transmission. |
| `tracking_id` | string | null | no | `None` | Optional external tracking identifier for this flow. |
| `confirmation_token` | string | null | no | `None` | Confirmation token returned by a prior pending response. |

## `update_directory_line`

Partially update a directory line (PATCH /ligne-annuaire/id-instance:{id-instance}).
Only provided fields are modified.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the directory line. |
| `matricule_plateforme` | string | null | no | `None` | New Approved Platform registration number. |
| `date_fin_effet` | string | null | no | `None` | New effective end date, ISO YYYY-MM-DD. |

## `update_routing_code`

Partially update a routing code (PATCH /code-routage/id-instance:{id-instance}).
Only provided fields are modified.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `id_instance` | string | yes |  | Directory instance ID (idInstance) of the routing code. |
| `type_identifiant_routage` | string | null | no | `None` | New 4-digit type code. Omit to leave unchanged. |
| `libelle_code_routage` | string | null | no | `None` | New label. Omit to leave unchanged. |
| `etat_administratif` | string | null | no | `None` | New status. Omit to leave unchanged. |

## `update_webhook`

Update a webhook subscription's technical parameters (authentication,
signature, custom headers). Metadata filters (flow type, direction)
cannot be changed; delete and recreate the webhook instead.

Only provided fields are modified (PATCH semantics).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `webhook_uid` | string | yes |  | UUID of the webhook subscription to update. |
| `auth_type` | string | null | no | `None` | New authentication type for the callback: BASIC or OAUTH2. |
| `auth_user_id` | string | null | no | `None` | User ID for BASIC authentication. |
| `auth_user_password` | string | null | no | `None` | Password for BASIC authentication. |
| `auth_token_url` | string | null | no | `None` | Token URL for OAUTH2 authentication. |
| `auth_client_id` | string | null | no | `None` | Client ID for OAUTH2 authentication. |
| `auth_client_secret` | string | null | no | `None` | Client secret for OAUTH2 authentication. |
| `signature_algo` | string | null | no | `None` | New signature algorithm. |
| `signature_key` | string | null | no | `None` | New base64-encoded signing key. |

## `validate_ereporting_xml`

Validate a DGFiP e-reporting (Flux 10) FRR XML payload.

Scope: XSD schema validation only, no business-rule checks. See README "Scope" section.

Checks the XML against the DGFiP Spécifications Externes v3.2 ereporting.xsd.
Returns validation result with errors if any. Use this before submitting to
catch structural problems early.

Validation levels (in order of preference):
  - xsd           — full schema validation
  - wellformedness — XML failed to parse (malformed or unsafe input)
  - none          — XSD files not found on disk

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  | FRR XML content to validate. Must be a complete Report document per DGFiP Spécifications Externes v3.2 ereporting.xsd. |

## `validate_facturx`

Validate a Factur-X CII XML document against its profile's Schematron ruleset.

Scope: Schematron (SVRL) business-rule validation only, no XSD structural
check. Returns is_valid, errors, and warnings (rule_id, location, text).
Use this before embedding the XML into a PDF/A-3 or submitting via submit_flow.

Requires the optional `saxonche` extra (FR-XSLT2-1, resolved in
mcp-einvoicing-core 1.14.0): the bundled Factur-X 1.09.2 Schematron
stylesheets require XSLT 2.0, which lxml/libxslt (XSLT 1.0 only) cannot
compile. Install with `pip install mcp-facture-electronique-fr[xslt2]`.
If it is missing, this tool returns level="unavailable" with
is_valid=None instead of raising.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  | Factur-X CII XML content to validate (the embedded XML, not the PDF/A-3). |
| `profile` | string | yes |  | Factur-X profile to validate against. One of: MINIMUM, BASICWL, BASIC, EN16931, EXTENDED, EXTENDED-CTC-FR. EXTENDED-CTC-FR is validated against the generic EXTENDED ruleset only — AFNOR has not published a CTC-FR-specific Schematron; French-specific rules beyond EXTENDED are not checked. |
