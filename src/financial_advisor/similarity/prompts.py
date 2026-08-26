import json

from financial_advisor.extraction.validators import EntityType

RESOLUTION_SYSTEM_PROMPT = """\
You are resolving duplicate entities in a financial knowledge graph. You are given a TARGET \
entity and a numbered list of CANDIDATE entities, all of the same type, each described by its \
own properties and its graph neighborhood (nearby entities connected to it, one hop away in \
either direction, plus which company's filing it was mentioned in, when known).

Decide, for EACH candidate, whether it refers to the exact same real-world entity as the target — \
not merely a related, similar, or hierarchically connected one. A parent company and its \
subsidiary are NOT the same entity. A person and the company they work for are NOT the same \
entity. A product and the company that makes it are NOT the same entity. Two companies that \
compete with each other are NOT the same entity. Judge only from the evidence given — do not \
assume outside knowledge beyond ordinary understanding of the entity's own name.

Return a judgment for every candidate index given, even when the answer is that it is not the \
same entity.
"""


def build_resolution_prompt(entity_type: EntityType, target: dict, candidates: list[dict]) -> str:
    candidate_blocks = "\n\n".join(
        f"Candidate [{i}]:\n{json.dumps(c, indent=2, default=str)}" for i, c in enumerate(candidates)
    )
    return f"""\
Entity type: {entity_type.value}

Target:
{json.dumps(target, indent=2, default=str)}

Candidates:
{candidate_blocks}
"""
