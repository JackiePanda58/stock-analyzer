"""Macro analyst agent for scenario analysis."""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

def create_macro_analyst(llm, tools):
    def macro_analyst_node(state) -> dict:
        current_date = state.get("trade_date", "")
        ticker = state["company_of_interest"]
        messages = state["messages"]
        system_msg = """You are a macro analyst. Analyze macro environment and policy risks.
Provide three scenarios (bullish 20%, neutral 50%, bearish 30%) with trigger conditions and impact.
Cover: fiscal policy, monetary policy, industry regulation, trade policy."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg + "\nDate: " + current_date + "\nTarget: " + ticker),
            MessagesPlaceholder(variable_name="messages"),
        ])
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke({"messages": messages})
        return {"messages": [result], "macro_report": result.content if not result.tool_calls else ""}
    return macro_analyst_node
