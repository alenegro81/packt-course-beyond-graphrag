from financial_advisor.extraction.validators import EntityType, ExtractedEntity, RelationshipType

ENTITY_TYPES = ", ".join(t.value for t in EntityType)
RELATIONSHIP_TYPES = ", ".join(t.value for t in RelationshipType)

# Scope/role preamble shared by the entity and reflection prompts — keeps both calls anchored to
# the same closed type vocabulary instead of letting the model improvise labels per call.
EXTRACTION_SCOPE = f"""\
You are a financial analyst extracting structured knowledge from a company's SEC 10-K filing. \
Extract only entities of these types: {ENTITY_TYPES}. Use the exact type names given. Do not \
invent other types. Extract only entities explicitly named in the text — do not infer entities \
that are merely implied. Use each entity's name exactly as it appears in the text, EXCEPT strip \
a leading list/bullet marker (e.g. "-", "•", "*", or a numbered/lettered prefix like "1." or \
"(a)") if one precedes the name — that's document formatting from how a table or list was laid \
out, not part of the entity's actual name (e.g. a row reading "- 3M Company" names the entity \
"3M Company", not "- 3M Company"). Set `resolved_string` equal to `string` for every entity in \
this pass — this pass does not attempt coreference resolution; that happens in reflection, once \
the settled entity list exists to resolve against.
"""

ENTITY_SYSTEM_PROMPT = EXTRACTION_SCOPE

# Coreference resolution lives in reflection, not the first pass, because it needs the settled
# entity list as evidence to resolve against — a first-pass-only rule can only special-case
# specific known patterns (e.g. a fixed filer id passed in from outside), which covers "the
# Company" but nothing else and needs a parameter threaded through every caller. Here, ANY
# mention that turns out to be a coreference of another entity already found gets caught: an
# abbreviation resolving to its spelled-out form just as readily as a filer's self-reference —
# and if the filer's own name (e.g. "3M") isn't extracted as an entity anywhere in this chunk,
# there's nothing to resolve "the Company" to here (that's a real limit of this approach,
# discussed in adr/0007's amendments — the earlier filer-id-based version didn't have it, but
# needed a parameter this one doesn't).
REFLECTION_COREFERENCE_GUIDANCE = """\
Some entities in the settled list above may be a coreference — a mention that's really just \
another way of referring to a DIFFERENT entity already in that list, not a distinct thing in \
its own right. The most common case in SEC filings: the filer defines a term for itself early \
on (e.g. "3M Company (the 'Company')") and then uses that term — "the Company", "the \
Registrant", "the Corporation" — throughout instead of its own name, so a Company-typed entity \
literally named "the Company" is usually standing in for whichever other Company entity in the \
list is actually the filer's name. The same idea applies to any type: an abbreviation standing \
in for its spelled-out form, for instance. Use the surrounding text as evidence for whether two \
entities are really the same thing.

For each entity that needs this correction, include it in your response with its `string` \
unchanged but `resolved_string` set to the OTHER entity's own `string` — copied exactly, and \
only ever the `string` of an entity that's actually in the settled list (of the SAME type as \
the one being corrected). Never invent a canonical form nobody extracted. Only include entities \
that need a correction or are newly found from the text — do not repeat an entity that needs no \
change.
"""


REFLECTION_SYSTEM_PROMPT = f"""\
{EXTRACTION_SCOPE}
You will be shown the source text and the settled entity list from the first pass. Check the \
text again for any entity of the allowed types the first pass missed, and return those as new \
entities.

{REFLECTION_COREFERENCE_GUIDANCE}
"""

RELATIONSHIP_SYSTEM_PROMPT = f"""\
You are a financial analyst extracting relationships between entities already identified in a \
company's SEC 10-K filing. Extract only relationships of these types: {RELATIONSHIP_TYPES}. Use \
the exact type names given. The source and target of every relationship MUST be one of the \
entity names given to you — never introduce an entity that isn't in that list. Only extract a \
relationship if the text explicitly states it; do not infer one from proximity alone. Include the \
verbatim sentence or phrase that supports each relationship as evidence.

"Explicitly states it" includes a table or list heading that applies to every row beneath it —
e.g. a subsidiaries exhibit titled "Consolidated subsidiaries of the Registrant:" followed by a
list of company names is an explicit SUBSIDIARY_OF statement for each one, even though no single
sentence repeats it per row; the heading is the statement, and it's evidence for every row, not
just the first. Do not withhold a relationship just because it's asserted once for a whole list
rather than restated per item — that's still an explicit statement, not an inference from
proximity. Proximity alone (two entities merely appearing near each other with no heading, label,
or sentence connecting them) is what to withhold on.
"""


def build_entity_prompt(chunk_text: str) -> str:
    return f"Text:\n{chunk_text}"


def build_reflection_prompt(chunk_text: str, first_pass_entities: list[ExtractedEntity]) -> str:
    # Type is included (not just the name) so the model can judge same-type coreference targets
    # itself, not just rely on the code-level backstop that also enforces it.
    found = "\n".join(f"  - {e.type.value}: {e.string}" for e in first_pass_entities) or "  (none)"
    return f"""\
Text:
{chunk_text}

Entities already found:
{found}
"""


def build_relationship_prompt(chunk_text: str, entity_names: list[str]) -> str:
    names = "\n".join(f"  - {name}" for name in entity_names)
    return f"""\
Text:
{chunk_text}

Known entities (relationships may only use these as source/target):
{names}
"""
