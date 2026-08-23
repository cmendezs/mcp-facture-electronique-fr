"""
MCP tools for Webhook management — XP Z12-013 Flow Service v1.2.0.

These tools allow subscribing to, listing, updating, and deleting
webhook notifications from the Approved Platform.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastmcp import FastMCP
from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from pydantic import Field

from mcp_facture_electronique_fr.tools.flow_tools import get_flow_client

logger = logging.getLogger(__name__)

WebhookFlowType = Literal[
    "CustomerInvoice",
    "SupplierInvoice",
    "StateInvoice",
    "CustomerInvoiceLC",
    "SupplierInvoiceLC",
    "StateCustomerInvoiceLC",
    "StateSupplierInvoiceLC",
    "AggregatedCustomerTransactionReport",
    "UnitaryCustomerTransactionReport",
    "AggregatedCustomerPaymentReport",
    "UnitaryCustomerPaymentReport",
    "UnitarySupplierTransactionReport",
    "MultiFlowReport",
]

WebhookFlowDirection = Literal["In", "Out"]

WebhookProcessingRule = Literal[
    "B2B",
    "B2BInt",
    "B2C",
    "B2G",
    "B2GInt",
    "OutOfScope",
    "B2GOutOfScope",
    "ArchiveOnly",
    "NotApplicable",
]

WebhookAckStatus = Literal["Pending", "Ok", "Error"]

WebhookAuthType = Literal["BASIC", "OAUTH2"]

WebhookSignatureAlgo = Literal[
    "RS256",
    "HS256",
    "ECDSA",
    "EDDSA_25519",
    "RSA_PSS",
    "EDDSA_448",
]


def register_webhook_tools(mcp: FastMCP) -> None:
    """Register the 5 Webhook Service tools on the FastMCP instance."""

    @mcp.tool()
    async def list_webhooks() -> dict:
        """
        List all webhook subscription IDs owned by the current OAuth2 token holder.

        Returns a list of webhook UUIDs. Use get_webhook with each ID to retrieve
        the full subscription details (callback URL, filters, authentication).
        """
        client = get_flow_client()
        return await client.list_webhooks()

    @mcp.tool()
    async def get_webhook(
        webhook_uid: Annotated[
            str,
            Field(
                description="UUID of the webhook subscription to retrieve.",
            ),
        ],
    ) -> dict:
        """
        Retrieve the full details of a webhook subscription: callback URL,
        authentication mode, signature configuration, and metadata filters
        (flow type, direction, processing rule, ack status).
        """
        client = get_flow_client()
        return await client.get_webhook(webhook_uid=webhook_uid)

    @mcp.tool()
    async def create_webhook(
        callback_url: Annotated[
            str,
            Field(
                description=(
                    "URL the Approved Platform will POST notifications to. "
                    "Must be HTTPS and reachable from the AP network."
                ),
            ),
        ],
        flow_type: Annotated[
            WebhookFlowType,
            Field(
                description=(
                    "Flow type to subscribe to: CustomerInvoice, SupplierInvoice, "
                    "CustomerInvoiceLC, SupplierInvoiceLC, "
                    "AggregatedCustomerTransactionReport, "
                    "UnitaryCustomerTransactionReport, "
                    "AggregatedCustomerPaymentReport, "
                    "UnitaryCustomerPaymentReport, "
                    "UnitarySupplierTransactionReport, MultiFlowReport, "
                    "StateInvoice, StateCustomerInvoiceLC, StateSupplierInvoiceLC."
                ),
            ),
        ],
        flow_direction: Annotated[
            WebhookFlowDirection,
            Field(
                description=(
                    "Direction filter: 'In' for incoming flows (from PDP to OD), "
                    "'Out' for outgoing flows (from OD to PDP)."
                ),
            ),
        ],
        processing_rule: Annotated[
            WebhookProcessingRule | None,
            Field(
                default=None,
                description="Optional processing rule filter: B2B, B2BInt, B2C, B2G, etc.",
            ),
        ] = None,
        ack_status: Annotated[
            WebhookAckStatus | None,
            Field(
                default=None,
                description="Optional acknowledgement status filter: Pending, Ok, Error.",
            ),
        ] = None,
        auth_type: Annotated[
            WebhookAuthType | None,
            Field(
                default=None,
                description="Authentication type for the callback: BASIC or OAUTH2.",
            ),
        ] = None,
        auth_user_id: Annotated[
            str | None,
            Field(
                default=None,
                description="User ID for BASIC authentication on the callback URL.",
            ),
        ] = None,
        auth_user_password: Annotated[
            str | None,
            Field(
                default=None,
                description="Password for BASIC authentication on the callback URL.",
            ),
        ] = None,
        auth_token_url: Annotated[
            str | None,
            Field(
                default=None,
                description="Token URL for OAUTH2 authentication on the callback.",
            ),
        ] = None,
        auth_client_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Client ID for OAUTH2 authentication on the callback.",
            ),
        ] = None,
        auth_client_secret: Annotated[
            str | None,
            Field(
                default=None,
                description="Client secret for OAUTH2 authentication on the callback.",
            ),
        ] = None,
        signature_algo: Annotated[
            WebhookSignatureAlgo | None,
            Field(
                default=None,
                description="Signature algorithm: RS256, HS256, ECDSA, EDDSA_25519, RSA_PSS, EDDSA_448.",
            ),
        ] = None,
        signature_key: Annotated[
            str | None,
            Field(
                default=None,
                description="Base64-encoded signing key for webhook payload verification.",
            ),
        ] = None,
        confirmation_token: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Confirmation token from a previous call. "
                    "Omit on the first call; supply on the second call to execute."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Subscribe to webhook notifications from the Approved Platform.

        The AP will POST event payloads to the callback URL whenever a flow
        matching the specified filters (flow type, direction, processing rule,
        ack status) is created or updated.

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="create_webhook",
                summary=(
                    f"Create webhook subscription: {flow_type} / {flow_direction} "
                    f"-> {callback_url}. "
                    "The AP will POST notifications to this URL."
                ),
                token=confirmation_token,
            )

        params: dict = {
            "callback": {"url": callback_url},
            "metadata": {
                "flowType": flow_type,
                "flowDirection": flow_direction,
            },
        }

        if processing_rule:
            params["metadata"]["processingRule"] = processing_rule
        if ack_status:
            params["metadata"]["ackStatus"] = ack_status

        if auth_type == "BASIC" and auth_user_id and auth_user_password:
            params["callback"]["authentication"] = {
                "authType": "BASIC",
                "userId": auth_user_id,
                "userPassword": auth_user_password,
            }
        elif auth_type == "OAUTH2" and auth_token_url and auth_client_id and auth_client_secret:
            params["callback"]["authentication"] = {
                "authType": "OAUTH2",
                "tokenUrl": auth_token_url,
                "clientId": auth_client_id,
                "clientSecret": auth_client_secret,
            }

        if signature_algo and signature_key:
            params["callback"]["signature"] = {
                "algo": signature_algo,
                "key": signature_key,
            }

        client = get_flow_client()
        result = await client.create_webhook(params=params)
        gate.consume(confirmation_token)
        return result

    @mcp.tool()
    async def update_webhook(
        webhook_uid: Annotated[
            str,
            Field(description="UUID of the webhook subscription to update."),
        ],
        auth_type: Annotated[
            WebhookAuthType | None,
            Field(
                default=None,
                description="New authentication type for the callback: BASIC or OAUTH2.",
            ),
        ] = None,
        auth_user_id: Annotated[
            str | None,
            Field(default=None, description="User ID for BASIC authentication."),
        ] = None,
        auth_user_password: Annotated[
            str | None,
            Field(default=None, description="Password for BASIC authentication."),
        ] = None,
        auth_token_url: Annotated[
            str | None,
            Field(default=None, description="Token URL for OAUTH2 authentication."),
        ] = None,
        auth_client_id: Annotated[
            str | None,
            Field(default=None, description="Client ID for OAUTH2 authentication."),
        ] = None,
        auth_client_secret: Annotated[
            str | None,
            Field(default=None, description="Client secret for OAUTH2 authentication."),
        ] = None,
        signature_algo: Annotated[
            WebhookSignatureAlgo | None,
            Field(default=None, description="New signature algorithm."),
        ] = None,
        signature_key: Annotated[
            str | None,
            Field(default=None, description="New base64-encoded signing key."),
        ] = None,
    ) -> dict:
        """
        Update a webhook subscription's technical parameters (authentication,
        signature, custom headers). Metadata filters (flow type, direction)
        cannot be changed; delete and recreate the webhook instead.

        Only provided fields are modified (PATCH semantics).
        """
        assert_not_read_only("FR_READ_ONLY")

        patch: dict = {}

        if auth_type == "BASIC" and auth_user_id and auth_user_password:
            patch["authentication"] = {
                "authType": "BASIC",
                "userId": auth_user_id,
                "userPassword": auth_user_password,
            }
        elif auth_type == "OAUTH2" and auth_token_url and auth_client_id and auth_client_secret:
            patch["authentication"] = {
                "authType": "OAUTH2",
                "tokenUrl": auth_token_url,
                "clientId": auth_client_id,
                "clientSecret": auth_client_secret,
            }

        if signature_algo and signature_key:
            patch["signature"] = {"algo": signature_algo, "key": signature_key}

        if not patch:
            return {
                "error": "No fields to update. Provide at least one of: authentication, signature."
            }

        client = get_flow_client()
        return await client.update_webhook(webhook_uid=webhook_uid, patch=patch)

    @mcp.tool()
    async def delete_webhook(
        webhook_uid: Annotated[
            str,
            Field(description="UUID of the webhook subscription to delete."),
        ],
        confirmation_token: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Confirmation token from a previous call. "
                    "Omit on the first call; supply on the second call to execute."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Delete (unsubscribe from) a webhook. After deletion, the AP will
        stop sending notifications to the callback URL.

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="delete_webhook",
                summary=(
                    f"Delete webhook subscription {webhook_uid!r}. "
                    "The AP will stop sending notifications to this webhook."
                ),
                token=confirmation_token,
            )

        client = get_flow_client()
        result = await client.delete_webhook(webhook_uid=webhook_uid)
        gate.consume(confirmation_token)
        return result
