"""
MCP tools for the Directory Service XP Z12-013 (Annex B v1.1.0).

These tools allow Claude to query and maintain the PPF directory:
searching companies (SIREN), establishments (SIRET), managing routing
codes, and directory lines (electronic invoicing receiving addresses).
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

from clients.directory_client import DirectoryClient

logger = logging.getLogger(__name__)

_directory_client: Optional[DirectoryClient] = None


def get_directory_client() -> DirectoryClient:
    global _directory_client
    if _directory_client is None:
        _directory_client = DirectoryClient()
    return _directory_client


def register_directory_tools(mcp: FastMCP) -> None:
    """Registers the 12 Directory Service tools on the FastMCP instance."""

    # ------------------------------------------------------------------
    # SIREN — Legal units
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_company(
        name: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Company name or trade name (partial search accepted). "
                    "Example: 'Dupont' will return all entities whose name contains 'Dupont'."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Company SIREN number (9 digits, no spaces). "
                    "Example: '123456789'."
                ),
            ),
        ] = None,
        status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Legal unit status in the PPF directory. "
                    "Possible values: Active, Inactive, Pending."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Pagination: only return entries updated after "
                    "this date/time (ISO 8601 format, e.g. 2024-09-01T00:00:00Z)."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Search for a company in the PPF directory by criteria (name, SIREN, status).
        Returns VAT-registered legal units recorded in the directory.
        At least one search criterion must be provided.
        """
        client = get_directory_client()
        return await client.search_company(
            name=name,
            siren=siren,
            status=status,
            updated_after=updated_after,
            limit=limit,
        )

    @mcp.tool()
    async def get_company_by_siren(
        siren: Annotated[
            str,
            Field(
                description=(
                    "Company SIREN number (9 digits, no spaces). "
                    "Example: '123456789'. "
                    "Returns the full legal unit information in the PPF directory, "
                    "including registration status and Approved Platform."
                )
            ),
        ],
    ) -> dict:
        """
        Look up a company in the PPF directory by its SIREN number.
        Returns the full legal unit information: company name,
        administrative status, associated Approved Platform, and registration dates.
        """
        client = get_directory_client()
        return await client.get_company_by_siren(siren=siren)

    # ------------------------------------------------------------------
    # SIRET — Establishments
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_establishment(
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Establishment SIRET number (14 digits, no spaces). "
                    "Example: '12345678900012'. "
                    "Use when you know the exact establishment; returns at most one result."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Parent company SIREN (9 digits). "
                    "Returns all establishments registered under this company. "
                    "Use to discover all SIRETs for a given SIREN."
                ),
            ),
        ] = None,
        administrative_status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Administrative status of the establishment in the PPF directory. "
                    "Active: establishment is open and reachable for invoicing. "
                    "Inactive: establishment is closed; invoices cannot be sent to it."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Pagination cursor: only return establishments updated after this "
                    "date/time (ISO 8601, e.g. 2024-09-01T00:00:00Z). "
                    "Use the 'nextUpdatedAfter' field from the previous response to fetch the next page."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results per page (1-500, default 50)."),
        ] = 50,
    ) -> dict:
        """
        Search for establishments (SIRETs) in the PPF directory by criteria.

        An establishment is a physical place of business activity identified by its 14-digit SIRET.
        Each company (SIREN) can have multiple establishments.

        BEHAVIOR:
        - Returns a paginated list of matching establishments; empty list if none match.
        - At least one search criterion should be provided; omitting all returns an error.
        - Pagination: if the response includes 'nextUpdatedAfter', pass it as updated_after to get the next page.

        RESPONSE: each item includes siret, siren, name, administrativeStatus (Active/Inactive),
        approvedPlatformId, and timestamps (createdAt, updatedAt).

        USAGE GUIDELINES:
        - Prefer get_establishment_by_siret when you already know the exact SIRET (faster, direct lookup).
        - Use search_establishment with siren to enumerate all establishments of a company.
        - Always verify administrativeStatus == Active before sending an invoice to that establishment.
        - Call this before create_directory_line to confirm the target SIRET is registered in the PPF directory.
        """
        client = get_directory_client()
        return await client.search_establishment(
            siret=siret,
            siren=siren,
            administrative_status=administrative_status,
            updated_after=updated_after,
            limit=limit,
        )

    @mcp.tool()
    async def get_establishment_by_siret(
        siret: Annotated[
            str,
            Field(
                description=(
                    "Establishment SIRET number (14 digits, no spaces). "
                    "Example: '12345678900012'. "
                    "Essential for verifying the receiving address before sending an invoice: "
                    "confirms the establishment is registered and active in the PPF directory."
                )
            ),
        ],
    ) -> dict:
        """
        Look up an establishment in the PPF directory by its SIRET number.
        Essential for verifying the receiving address before sending an invoice.
        Returns the establishment details, its status, and its Approved Platform.
        """
        client = get_directory_client()
        return await client.get_establishment_by_siret(siret=siret)

    # ------------------------------------------------------------------
    # Routing Code
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_routing_code(
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Establishment SIRET (14 digits). "
                    "Returns all routing codes associated with this establishment. "
                    "Most common filter: use when building a directory line for a specific SIRET."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Company SIREN (9 digits). "
                    "Returns routing codes for all establishments under this company."
                ),
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Exact routing code value to look up (e.g. 'ACCOUNTS-DEPT', 'REGION-WEST'). "
                    "Use to verify a routing code exists before referencing it in an invoice."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results per page (1-500, default 50)."),
        ] = 50,
    ) -> dict:
        """
        Search routing codes registered in the PPF directory for a recipient.

        Routing codes subdivide a SIRET receiving address to department or service level,
        allowing a company to route invoices to different internal units (e.g. purchasing, accounting).

        BEHAVIOR:
        - Returns a paginated list of matching routing codes; empty list if none defined for the criteria.
        - At least one of siret, siren, or routing_code should be provided.
        - A SIRET may have zero or more routing codes; zero means invoices go to the SIRET-level address.

        RESPONSE: each item includes instanceId, siret, siren, routingCode, label (optional), and timestamps.
        The instanceId is required to update or delete a routing code.

        USAGE GUIDELINES:
        - Call before create_directory_line with a routing_code to confirm the code exists on the target SIRET.
        - Call to enumerate available routing codes when helping a sender choose the correct recipient address.
        - If no routing codes exist for a SIRET, the invoice must be addressed at SIRET level without a routing code.
        - Use create_routing_code to create a new code; use update_routing_code with instanceId to rename it.
        """
        client = get_directory_client()
        return await client.search_routing_code(
            siret=siret,
            siren=siren,
            routing_code=routing_code,
            limit=limit,
        )

    @mcp.tool()
    async def create_routing_code(
        siret: Annotated[
            str,
            Field(
                description=(
                    "Establishment SIRET to associate this routing code with (14 digits). "
                    "The SIRET must already be registered and Active in the PPF directory."
                )
            ),
        ],
        routing_code: Annotated[
            str,
            Field(
                description=(
                    "Routing code value to create (free-form string, e.g. 'PURCHASING-DEPT', 'PARIS-OFFICE'). "
                    "This exact value will appear in invoicing addresses and must be communicated to senders."
                )
            ),
        ],
        label: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Human-readable label for the routing code (e.g. 'Purchasing department - HQ'). "
                    "Optional but recommended for clarity when multiple codes exist."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Create a new routing code for a SIRET in the PPF directory.

        Routing codes let a recipient company route incoming invoices to specific departments or services.
        Once created, the code can be referenced in a directory line (create_directory_line)
        and communicated to senders to use in invoice addressing.

        BEHAVIOR:
        - Returns the created routing code object including its instanceId.
        - Fails if the SIRET is not registered or not Active in the PPF directory.
        - Fails if a routing code with the same value already exists for this SIRET (duplicate check).
        - The routing_code value is case-sensitive and must be unique per SIRET.

        RESPONSE: includes instanceId (required for update/delete), siret, siren, routingCode, label, createdAt.

        USAGE GUIDELINES:
        - Call get_establishment_by_siret first to verify the SIRET is Active before creating a routing code.
        - After creating, call create_directory_line with routing_code set to register the receiving address.
        - If a routing code already exists (duplicate error), use search_routing_code to retrieve its instanceId,
          then update it with update_routing_code if needed.
        - Routing codes are optional; omit them if the company routes all invoices to a single SIRET address.
        """
        client = get_directory_client()
        return await client.create_routing_code(
            siret=siret,
            routing_code=routing_code,
            label=label,
        )

    @mcp.tool()
    async def update_routing_code(
        instance_id: Annotated[
            str,
            Field(
                description=(
                    "Instance identifier of the routing code to update "
                    "(returned by create_routing_code or search_routing_code)."
                )
            ),
        ],
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description="New routing code value.",
            ),
        ] = None,
        label: Annotated[
            Optional[str],
            Field(
                default=None,
                description="New descriptive label.",
            ),
        ] = None,
    ) -> dict:
        """
        Partially update an existing routing code in the PPF directory.
        Only the provided fields are modified (PATCH semantics).
        """
        client = get_directory_client()
        return await client.update_routing_code(
            instance_id=instance_id,
            routing_code=routing_code,
            label=label,
        )

    # ------------------------------------------------------------------
    # Directory Line
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_directory_line(
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Taxable entity SIREN (9 digits). "
                    "Returns all directory lines (at SIREN, SIRET, and routing-code level) "
                    "registered for this company. Most common starting point."
                ),
            ),
        ] = None,
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Specific establishment SIRET (14 digits). "
                    "Narrows results to lines for this establishment only."
                ),
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Filter by routing code associated with the directory line. "
                    "Use to find the exact line for a department-level address."
                ),
            ),
        ] = None,
        platform_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Filter by Approved Platform identifier. "
                    "Use to list all lines managed by a specific AP."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Pagination cursor: only return lines updated after this date/time "
                    "(ISO 8601, e.g. 2024-09-01T00:00:00Z). "
                    "Use the 'nextUpdatedAfter' field from the previous response to fetch the next page."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results per page (1-500, default 50)."),
        ] = 50,
    ) -> dict:
        """
        Search directory lines (electronic invoice receiving addresses) for a taxable entity.

        A directory line maps an addressing identifier (SIREN, SIREN/SIRET, or SIREN/SIRET/routing-code)
        to an Approved Platform and an optional technical address. It is the authoritative record
        of where the recipient wants to receive invoices.

        BEHAVIOR:
        - Returns a paginated list of matching directory lines; empty list if the entity has no registered lines.
        - At least one search criterion should be provided; omitting all may return an error or a very large result set.
        - Pagination: if the response contains 'nextUpdatedAfter', pass it as updated_after to retrieve the next page.
        - A recipient can have several lines (e.g. one at SIREN level plus specific ones per SIRET or routing code);
          the most specific line (SIREN/SIRET/routing-code) takes precedence over less specific ones.

        RESPONSE: each item includes instanceId, addressingIdentifier (SIREN[/SIRET[/routingCode]]),
        approvedPlatformId, technicalAddress (optional), and timestamps (createdAt, updatedAt).
        The instanceId is required for update_directory_line and delete_directory_line.

        USAGE GUIDELINES:
        - Prefer get_directory_line with the full addressingIdentifier when you know the exact address
          (faster, avoids pagination).
        - Use search_directory_line with siren to audit all receiving addresses of a company.
        - Call before sending an invoice to verify the recipient has a registered line and identify their AP.
        - If no lines are returned, the recipient is not yet registered in the PPF directory and cannot receive
          electronic invoices; they must register via create_directory_line or through their AP.
        - The instanceId from results is needed to call update_directory_line or delete_directory_line.
        """
        client = get_directory_client()
        return await client.search_directory_line(
            siren=siren,
            siret=siret,
            routing_code=routing_code,
            platform_id=platform_id,
            updated_after=updated_after,
            limit=limit,
        )

    @mcp.tool()
    async def get_directory_line(
        addressing_identifier: Annotated[
            str,
            Field(
                description=(
                    "Addressing identifier of the directory line. "
                    "Format: SIREN alone (e.g. '123456789'), "
                    "SIREN/SIRET (e.g. '123456789/12345678900012'), "
                    "or SIREN/SIRET/routing-code (e.g. '123456789/12345678900012/PURCHASING-DEPT'). "
                    "Use before any invoice submission to verify "
                    "recipient reachability and their Approved Platform."
                )
            ),
        ],
    ) -> dict:
        """
        Look up a directory line by its addressing identifier.
        Use before any invoice submission to verify recipient reachability
        and obtain their receiving Approved Platform.
        Returns 404 if the recipient is not yet registered in the PPF directory.
        """
        client = get_directory_client()
        return await client.get_directory_line(addressing_identifier=addressing_identifier)

    @mcp.tool()
    async def create_directory_line(
        siren: Annotated[
            str,
            Field(
                description="SIREN of the taxable entity (9 digits) creating this receiving address."
            ),
        ],
        platform_id: Annotated[
            str,
            Field(
                description=(
                    "Identifier of the Approved Platform that will receive the invoices "
                    "(provided by your AP upon registration)."
                )
            ),
        ],
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Specific establishment SIRET (14 digits). "
                    "If absent, the line applies to all establishments under the SIREN."
                ),
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Routing code to refine the receiving address "
                    "(must exist via create_routing_code)."
                ),
            ),
        ] = None,
        technical_address: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "AP-specific technical receiving address "
                    "(endpoint, mailbox, etc.). "
                    "Format defined by the Approved Platform."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Create a directory line (electronic invoice receiving address)
        for a taxable entity. Required to register in the PPF directory and
        allow other companies to send you electronic invoices.
        A line can be at SIREN level (entire company), SIREN/SIRET
        (one establishment), or SIREN/SIRET/routing-code (a specific department).
        """
        client = get_directory_client()
        return await client.create_directory_line(
            siren=siren,
            platform_id=platform_id,
            siret=siret,
            routing_code=routing_code,
            technical_address=technical_address,
        )

    @mcp.tool()
    async def update_directory_line(
        instance_id: Annotated[
            str,
            Field(
                description=(
                    "Instance identifier of the directory line to update "
                    "(returned by create_directory_line or search_directory_line)."
                )
            ),
        ],
        platform_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "New Approved Platform identifier. "
                    "Use when changing AP (with delete_directory_line on the old one)."
                ),
            ),
        ] = None,
        technical_address: Annotated[
            Optional[str],
            Field(
                default=None,
                description="New technical receiving address.",
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description="New associated routing code.",
            ),
        ] = None,
    ) -> dict:
        """
        Partially update an existing directory line.
        Only the provided fields are modified (PATCH semantics).
        Typically used to update the technical address after a
        configuration change on the Approved Platform side.
        """
        client = get_directory_client()
        return await client.update_directory_line(
            instance_id=instance_id,
            platform_id=platform_id,
            technical_address=technical_address,
            routing_code=routing_code,
        )

    @mcp.tool()
    async def delete_directory_line(
        instance_id: Annotated[
            str,
            Field(
                description=(
                    "Instance identifier of the directory line to delete "
                    "(returned by create_directory_line or search_directory_line). "
                    "WARNING: this action is permanent. After deletion, "
                    "senders will no longer be able to send you invoices via this address."
                )
            ),
        ],
    ) -> dict:
        """
        Delete a directory line. Use when changing Approved Platform
        or closing an establishment. After deletion, create a new line
        via create_directory_line if needed.
        WARNING: irreversible action — verify the instance_id before calling this tool.
        """
        client = get_directory_client()
        return await client.delete_directory_line(instance_id=instance_id)
