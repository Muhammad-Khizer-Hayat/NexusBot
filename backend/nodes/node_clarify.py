# backend/nodes/node_clarify.py
# Node 3d: Asks clarifying questions when user input is too vague

from agents.state import AgentState

CLARIFY_RESPONSES = {
    "can you help": (
        "Of course! I'm happy to help 😊\n\n"
        "What would you like help with? For example:\n"
        "- 🌐 **Web search** — *'Who is the CEO of Tesla?'*\n"
        "- 🌤️ **Weather** — *'What is the weather in Lahore?'*\n"
        "- 💻 **Coding** — *'Write a Python function to sort a list'*\n"
        "- 🧮 **Math** — *'What is 18% of 75000?'*\n"
        "- 📚 **General knowledge** — *'Tell me about LangGraph'*\n\n"
        "Just type your question and I'll get right on it!"
    ),
    "default": (
        "I'd love to help! Could you give me a bit more detail about what you need?\n\n"
        "For example, are you looking for:\n"
        "- 🔍 Information or research on a topic?\n"
        "- 💻 Help with code or a technical problem?\n"
        "- 🌤️ Weather for a specific city?\n"
        "- 🧮 A calculation or math problem?\n"
        "- 📄 Something from your uploaded documents?\n\n"
        "Tell me more and I'll give you the best answer!"
    )
}

def clarify_node(state: AgentState) -> AgentState:
    """
    Node 3d — Clarify
    Returns a helpful clarifying question when user input is too vague.
    No LLM call needed — saves API quota.
    """
    msg = state["input"].lower().strip()

    # Pick the most relevant clarifying response
    if any(w in msg for w in ["help", "assist", "question", "ask"]):
        response = CLARIFY_RESPONSES["can you help"]
    else:
        response = CLARIFY_RESPONSES["default"]

    print(f"[Node 3d] Clarifying vague input: '{state['input']}'")
    return {**state, "output": response}