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
                    "Example: '12345678900012'."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Parent company SIREN (9 digits). "
                    "Returns all establishments of this company."
                ),
            ),
        ] = None,
        administrative_status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Administrative status of the establishment. "
                    "Values: Active (open), Inactive (closed)."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description="ISO 8601 pagination (e.g. 2024-09-01T00:00:00Z).",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Search for an establishment in the PPF directory by criteria
        (SIRET, parent SIREN, administrative status).
        An establishment corresponds to a place of business activity (SIRET).
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
                    "Returns all routing codes associated with this establishment."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Company SIREN (9 digits).",
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Routing code value to search for (e.g. 'ACCOUNTS-DEPT', 'REGION-WEST')."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Search routing codes for a recipient in the PPF directory.
        Routing codes refine the receiving address at service or department level
        for companies that want to route incoming invoices.
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
                    "Establishment SIRET to associate this routing code with (14 digits)."
                )
            ),
        ],
        routing_code: Annotated[
            str,
            Field(
                description=(
                    "Routing code value to create (free-form string, e.g. 'PURCHASING-DEPT', 'PARIS-OFFICE'). "
                    "This code will be used in the recipient's invoicing address."
                )
            ),
        ],
        label: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Descriptive label for the routing code (e.g. 'Purchasing department - HQ').",
            ),
        ] = None,
    ) -> dict:
        """
        Create a routing code for a SIRET in the PPF directory.
        The routing code refines the invoice receiving address
        at the service or department level of the recipient company.
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
                    "Returns all directory lines registered for this company."
                ),
            ),
        ] = None,
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Specific establishment SIRET (14 digits).",
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filter by routing code associated with the directory line.",
            ),
        ] = None,
        platform_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filter by Approved Platform identifier.",
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description="ISO 8601 pagination (e.g. 2024-09-01T00:00:00Z).",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Maximum number of results (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Search directory lines (electronic invoicing receiving addresses) for a taxable entity.
        A directory line is the address at which the recipient wishes to receive invoices
        (identified by SIREN, SIREN/SIRET, or SIREN/SIRET/routing-code).
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
