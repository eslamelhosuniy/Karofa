from string import Template

#### CHAT HISTORY PROMPTS ####

#### Query Rewrite ####

query_rewrite_system = Template("\n".join([
    "You are a query rewriting assistant.",
    "Your task is to rewrite the user's current query to be self-contained and contextual.",
    "Incorporate relevant context from the chat history into the query.",
    "The rewritten query should be clear and standalone.",
    "Do NOT answer the query, only rewrite it.",
    "Output ONLY the rewritten query, nothing else.",
]))

query_rewrite_prompt = Template("\n".join([
    "## Chat History (last messages):",
    "$chat_history",
    "",
    "## Session Entities:",
    "$session_entities",
    "",
    "## Current User Query:",
    "$query",
    "",
    "## Rewritten Query:",
]))

#### Entity Extraction ####

entity_extraction_system = Template("\n".join([
    "You are an entity extraction assistant.",
    "Extract important entities from the conversation (names, topics, concepts, dates, etc).",
    "Return ONLY a JSON array of strings with the entities.",
    "Example output: [\"entity1\", \"entity2\", \"entity3\"]",
    "Keep entities concise and relevant.",
    "Maximum 10 entities total.",
]))

entity_extraction_prompt = Template("\n".join([
    "## User Query:",
    "$query",
    "",
    "## Assistant Answer:",
    "$answer",
    "",
    "## Existing Entities:",
    "$existing_entities",
    "",
    "## Updated Entities (JSON array):",
]))
