import logging

import instructor

from app.config import get_settings
# from app.services.extraction.models import ContractChunkExtraction
from app.services.extraction.models import ContractChunkSemanticExtraction

logger = logging.getLogger(__name__)


class ContractExtractor:
    def __init__(self) -> None:
        settings = get_settings()

        self.model = settings.extraction_model

        self.client = instructor.from_provider(
            "ollama/qwen2.5",
            base_url=settings.ollama_base_url,
            mode=instructor.Mode.JSON,
        )

    def extract(
        self,
        chunk_text: str,
    ) -> ContractChunkSemanticExtraction:

    
        system_prompt = """
You extract factual information from legal contract text.

Use ONLY the supplied document chunk.
Do not use outside knowledge.
Do not guess or infer.
If the text does not clearly support an item, do not extract it.

IMPORTANT:
- Every extracted item MUST contain source_text.
- source_text MUST be copied from the supplied chunk.
- Never invent source_text.
- Do not omit source_text.
- Do not create information that is not explicitly present.

EXTRACT ONLY:

1. PARTIES

Extract people, companies, or organizations explicitly identified as
contracting parties.

For each party:
- name = exact party name or party description
- designation = explicit label or alias assigned to that party, if present
- source_text = exact supporting text

Example:
'ArmorBlox, Inc. ("Armorblox")'
→ name = 'ArmorBlox, Inc.'
→ designation = 'Armorblox'

'the company subscribing to the Services ("Customer")'
→ name = 'the company subscribing to the Services'
→ designation = 'Customer'

Do NOT invent roles such as Vendor, Provider, Client, Seller, Buyer, or User.

2. DEFINED TERMS

Extract ONLY terms explicitly defined in this chunk.

Accept definitions using wording such as:
- "X" means ...
- "X" shall mean ...
- "X" refers to ...
- "X" includes ...

For each:
- term
- definition
- source_text

Do NOT extract:
'the Services (as defined below)'
because the definition is not present in this chunk.

3. OBLIGATIONS

Extract explicit duties, requirements, or prohibitions.

Common signals:
shall, must, required to, agrees to, shall not, may not,
responsible for.

For each:
- party
- action
- object, if explicit
- condition, if explicit
- deadline, if explicit
- source_text

Do not infer an obligation.

4. RIGHTS

Extract explicit permissions or rights.

Common signals:
may, has the right to, is entitled to, grants the right to,
permitted to.

For each:
- party
- action
- condition, if explicit
- deadline, if explicit
- source_text

Do not infer a right.

5. REFERENCES

Extract explicit references to contractual information.

Examples:
Section 2.3
Section 9
1.4
Applicable Laws
Order Form
Exhibit A
this Agreement
the foregoing
as described above

For each:
- target
- reference_type
- source_text

Use one of:
section_reference
defined_term_reference
order_form_reference
exhibit_reference
agreement_reference
other_contract_reference

DO NOT EXTRACT:
- clauses
- section titles
- section numbers
- document hierarchy
- summaries
- legal conclusions

Those are handled separately.

When nothing is explicitly supported, return an empty list.

Return ONLY the structured data required by the schema.
"""



        user_prompt = f"""
Extract the contractual information from this document chunk.

DOCUMENT CHUNK
---------------
{chunk_text}
---------------
"""

        logger.info(
            "[ContractExtractor] Sending chunk to %s (%d chars)",
            self.model,
            len(chunk_text),
        )

        result = self.client.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_model=ContractChunkSemanticExtraction,
            max_retries=2,
            timeout=300.0,
            temperature=0,
        )

      
        logger.info(
            "[ContractExtractor] Extraction successful: "
            "parties=%d defined_terms=%d obligations=%d rights=%d references=%d",
            len(result.parties),
            len(result.defined_terms),
            len(result.obligations),
            len(result.rights),
            len(result.references),
        )
        return result