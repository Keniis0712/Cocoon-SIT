from app.models.entities import PromptTemplateType


PROMPT_VARIABLES_BY_TYPE: dict[str, dict[str, str]] = {
    PromptTemplateType.system: {
        "character_settings": "Structured character settings and prompt summary.",
        "session_state": "Current dynamic session state.",
        "provider_capabilities": "Resolved provider/model capabilities.",
    },
    PromptTemplateType.meta: {
        "character_settings": "Structured character settings and prompt summary.",
        "session_state": "Current dynamic session state.",
        "visible_messages": "Recent visible dialogue messages.",
        "memory_context": "Retrieved long-term memory snippets.",
        "runtime_event": "Current runtime event payload.",
        "wakeup_context": "Wakeup-specific runtime context when the current event is a wakeup.",
        "merge_context": "Merge-specific context when the current event is a merge.",
        "provider_capabilities": "Resolved provider/model capabilities.",
    },
    PromptTemplateType.generator: {
        "character_settings": "Structured character settings and prompt summary.",
        "session_state": "Current dynamic session state.",
        "visible_messages": "Recent visible dialogue messages.",
        "memory_context": "Retrieved long-term memory snippets.",
        "runtime_event": "Current runtime event payload.",
        "wakeup_context": "Wakeup-specific runtime context when the current event is a wakeup.",
        "merge_context": "Merge-specific context when the current event is a merge.",
        "provider_capabilities": "Resolved provider/model capabilities.",
    },
    PromptTemplateType.memory_summary: {
        "visible_messages": "Recent visible dialogue messages.",
        "memory_context": "Retrieved long-term memory snippets.",
    },
    PromptTemplateType.pull: {
        "runtime_event": "Pull event payload.",
        "memory_context": "Candidate memory context.",
    },
    PromptTemplateType.merge: {
        "runtime_event": "Merge event payload.",
        "merge_context": "Merge-specific context.",
    },
    PromptTemplateType.audit_summary: {
        "runtime_event": "Event and run metadata.",
        "visible_messages": "Visible messages included in the run.",
    },
}


DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    PromptTemplateType.system: (
        "System Template",
        "You are operating inside Cocoon-SIT.\nCharacter:\n{{ character_settings }}\nSession:\n{{ session_state }}\nProvider:\n{{ provider_capabilities }}",
    ),
    PromptTemplateType.meta: (
        "Meta Template",
        "Review the current event and decide whether to reply.\nEvent:\n{{ runtime_event }}\nMessages:\n{{ visible_messages }}\nMemory:\n{{ memory_context }}\nSession:\n{{ session_state }}",
    ),
    PromptTemplateType.generator: (
        "Generator Template",
        "Generate the assistant reply for the current cocoon.\nCharacter:\n{{ character_settings }}\nSession:\n{{ session_state }}\nMessages:\n{{ visible_messages }}\nMemory:\n{{ memory_context }}\nEvent:\n{{ runtime_event }}",
    ),
    PromptTemplateType.memory_summary: (
        "Memory Summary Template",
        "Summarize durable memory from the latest visible messages.\nMessages:\n{{ visible_messages }}\nExisting memory:\n{{ memory_context }}",
    ),
    PromptTemplateType.pull: (
        "Pull Template",
        "Summarize pull candidates.\nEvent:\n{{ runtime_event }}\nMemory:\n{{ memory_context }}",
    ),
    PromptTemplateType.merge: (
        "Merge Template",
        "Summarize merge candidates.\nEvent:\n{{ runtime_event }}\nMerge context:\n{{ merge_context }}",
    ),
    PromptTemplateType.audit_summary: (
        "Audit Summary Template",
        "Summarize the run.\nEvent:\n{{ runtime_event }}\nMessages:\n{{ visible_messages }}",
    ),
}
