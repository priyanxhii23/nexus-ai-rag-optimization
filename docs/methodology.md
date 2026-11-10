# Methodology

## Retrieval (RAG)
* Extraction: `pypdf` per page (page numbers kept for citations); TXT/MD decoded as UTF-8 (fallbacks UTF-16, cp1252).
* Chunking: paragraphs → sentences → words, packed to ~900 characters with ~150 characters of overlap.
* Embeddings: `all-MiniLM-L6-v2`, 384 dimensions, L2-normalised (cosine = dot product).
* Vector store: ChromaDB (cosine space). Every query is filtered by `tenant_id` and the selected document IDs.
* Relevance floor: passages below `min_retrieval_score` (default 0.30) are ignored. If nothing remains,
  the answer is "the documents do not contain enough information" **without** an LLM call.
* Prompt: documents go in the user message inside `<document>` blocks with neutralised markup; the system
  prompt says they are untrusted data; chunks matching injection patterns are flagged.

## Semantic cache
1. Exact match on the normalised question (lower-case, whitespace collapsed, trailing punctuation removed).
2. Semantic match: nearest cached questions (same tenant **and** same document scope) by cosine similarity.
3. A candidate is reused only if **all** checks pass: similarity ≥ threshold; not expired (TTL); every
   source document still exists, has the same version and belongs to the tenant; same answer mode
   (mock vs real); compatible intent (same category, same numbers, same negation, no conflicting
   qualifier such as "after" vs "within").
4. Updating or deleting a document invalidates every cache entry that used it.

Why the intent guard exists - measured with the real model (see `docs/evaluation.md`):
"Can I get a refund **after** 30 days?" vs "... **within** 30 days?" has cosine similarity **0.984**, and
"Which plan includes phone support?" vs "Which plans **do not** include phone support?" 0.949. No
threshold can separate these; the guard does.

## Query intelligence & routing
* Keyword/regex signals pick a category (priority: multi-step, mathematical, comparative, analytical,
  conceptual, factual). Complexity score = category base + length + mixed reasoning + linked clauses,
  capped at 100 → simple < 35 ≤ medium < 65 ≤ complex.
* Strategy maps level → tier (balanced: simple→small, medium→medium, complex→large). Missing tier →
  nearest tier (prefer more capable). Remaining models form the fallback chain.

## Costs
* Tokens: provider-reported when the API returns usage; otherwise estimated (~4 characters per token) and labelled.
* Cost = input tokens × input price + output tokens × output price (per million), long-context tier when defined.
* Claude prices: Anthropic list prices; Gemini/OpenAI-compatible: entered by the user, otherwise "unpriced".
* Mock models are priced like the real model they stand in for and labelled **simulated**.
* Savings are counterfactual: cache saving = original cost of the reused answer; routing saving = same
  tokens on the most capable available model minus the actual cost.
