from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


from typing import Any

from pydantic import Field


def edge(label: str, **kwargs: Any) -> Any:
    """
    Define a Docling Graph relationship while preserving
    Pydantic defaults/default_factory.
    """

    field_kwargs = dict(kwargs)

    field_kwargs["json_schema_extra"] = {
        "edge_label": label,
        **field_kwargs.pop("json_schema_extra", {}),
    }

    return Field(**field_kwargs)

# ---------------------------------------------------------
# PARTY
# ---------------------------------------------------------


class Party(BaseModel):
    """
    A named legal party to the agreement.

    Use the party name exactly as written in the contract.
    Examples: "ArmorBlox, Inc.", "Customer", "Vendor".
    """

    model_config = ConfigDict(
        is_entity=True,
        graph_id_fields=["name"],
    )

    name: str = Field(
        description=(
            "Exact party name as written in the contract. "
            "Do not invent or normalize the name."
        ),
        examples=[
            "ArmorBlox, Inc.",
            "Customer",
            "Vendor",
        ],
    )

    role: str | None = Field(
        default=None,
        description=(
            "The contractual role of this party when explicitly stated."
        ),
    )


# ---------------------------------------------------------
# DEFINED TERM
# ---------------------------------------------------------


class DefinedTerm(BaseModel):
    """
    A term explicitly defined by the contract.

    Examples: "Agreement", "Services", "Affiliate", "Material Breach".
    """

    model_config = ConfigDict(
        is_entity=True,
        graph_id_fields=["term"],
    )

    term: str = Field(
        description=(
            "The exact defined term as written, without changing its wording."
        ),
        examples=[
            "Agreement",
            "Services",
            "Applicable Laws",
            "Material Breach",
        ],
    )

    definition: str | None = Field(
        default=None,
        description=(
            "The definition assigned to the term by the contract."
        ),
    )


# ---------------------------------------------------------
# OBLIGATION
# ---------------------------------------------------------


class Obligation(BaseModel):
    """
    A contractual duty contained inside a clause.

    This is a component, not a standalone graph entity.
    """

    model_config = ConfigDict(
        is_entity=False,
    )

    action: str | None = Field(
        default=None,
        description="The required action, stated in concise terms.",
    )

    object: str | None = Field(
        default=None,
        description="The object or thing affected by the action.",
    )

    condition: str | None = Field(
        default=None,
        description="Condition under which the obligation applies.",
    )

    deadline: str | None = Field(
        default=None,
        description="Deadline, duration, frequency, or timing requirement.",
    )

    party: Party | None = edge(
        label="IMPOSES_ON",
        reference=True,
        default=None,
        description="Party responsible for this obligation.",
    )


# ---------------------------------------------------------
# RIGHT
# ---------------------------------------------------------


class Right(BaseModel):
    """
    A contractual right granted to a party and expressed inside a clause.

    This is a component, not a standalone graph entity.
    """

    model_config = ConfigDict(
        is_entity=False,
    )

    action: str | None = Field(
        default=None,
        description="The action the party is permitted to take.",
    )

    condition: str | None = Field(
        default=None,
        description="Condition or trigger for exercising the right.",
    )

    deadline: str | None = Field(
        default=None,
        description="Time limit for exercising the right, when stated.",
    )

    party: Party | None = edge(
        label="GRANTED_TO",
        reference=True,
        default=None,
        description="Party receiving this contractual right.",
    )


# ---------------------------------------------------------
# CLAUSE
# ---------------------------------------------------------


class Clause(BaseModel):
    """
    A named or numbered contractual provision.

    Prefer a printed section/clause identifier such as "1.1" or
    "9.2"; when the document has no number, use its short printed heading.
    """

    model_config = ConfigDict(
        is_entity=True,
        graph_id_fields=["locator"],
    )

    locator: str = Field(
        description=(
            "Exact short clause/section identifier from the document, "
            "such as '1.1', '9.2', 'ARTICLE VII', or a short printed heading "
            "when no number is present."
        ),
        examples=[
            "1.1",
            "3.2",
            "9.2",
            "ARTICLE VII",
            "Termination",
        ],
    )

    title: str | None = Field(
        default=None,
        description="Short title of the provision, when present.",
    )

    clause_type: str | None = Field(
        default=None,
        description=(
            "Subject of the provision, such as definitions, payment, "
            "services, confidentiality, termination, liability, or indemnity."
        ),
    )

    text: str | None = Field(
        default=None,
        description="Relevant contractual text of the provision.",
    )

    applies_to: list[Party] = edge(
        label="APPLIES_TO",
        reference=True,
        default_factory=list,
        description="Parties to whom this clause applies.",
    )

    defines: list[DefinedTerm] = edge(
        label="DEFINES",
        reference=True,
        default_factory=list,
        description="Defined terms established by this clause.",
    )

    references: list[Clause] = edge(
        label="REFERENCES",
        reference=True,
        default_factory=list,
        description="Other clauses explicitly referenced by this clause.",
    )

    depends_on: list[Clause] = edge(
        label="DEPENDS_ON",
        reference=True,
        default_factory=list,
        description=(
            "Other contractual provisions needed to interpret or apply this clause."
        ),
    )

    modifies: list[Clause] = edge(
        label="MODIFIES",
        reference=True,
        default_factory=list,
        description="Other provisions this clause modifies or overrides.",
    )

    exceptions_to: list[Clause] = edge(
        label="EXCEPTION_TO",
        reference=True,
        default_factory=list,
        description="Other provisions for which this clause creates an exception.",
    )

    obligations: list[Obligation] = Field(
        default_factory=list,
        description="Contractual duties expressed by this clause.",
    )

    rights: list[Right] = Field(
        default_factory=list,
        description="Contractual rights expressed by this clause.",
    )


# ---------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------


class Contract(BaseModel):
    """
    Root entity representing one legal contract.

    It contains the canonical parties, clauses, and defined terms.
    """

    model_config = ConfigDict(
        is_entity=True,
        graph_id_fields=["title"],
    )

    title: str = Field(
        description="Exact title of the contract.",
        examples=[
            "Master SaaS Agreement",
            "Software Services Agreement",
        ],
    )

    parties: list[Party] = edge(
        label="HAS_PARTY",
        default_factory=list,
        description="Legal parties to the contract.",
    )

    clauses: list[Clause] = edge(
        label="HAS_CLAUSE",
        default_factory=list,
        description="Named or numbered contractual provisions.",
    )

    defined_terms: list[DefinedTerm] = edge(
        label="HAS_DEFINED_TERM",
        default_factory=list,
        description="Defined terms used by the contract.",
    )


Contract.model_rebuild()
Clause.model_rebuild()