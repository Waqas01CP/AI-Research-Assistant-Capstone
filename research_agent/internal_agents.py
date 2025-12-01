from google.adk.agents import Agent, BaseAgent
from google.adk.tools import google_search
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
from typing import AsyncGenerator
from .config import worker_model, critic_model

# --- SYNTHESIS ---
intent_synthesis_agent = Agent(
    name="IntentSynthesisAgent",
    model=critic_model,
    instruction="""You are a Lead Research Architect.
    
    INPUT: A conversation history containing a Research Topic and specific user answers regarding Focus and Audience.
    
    TASK: Synthesize this into a 'Master Research Directive'.
    - This directive must be extremely detailed.
    - Explicitly state the technical depth required (e.g., 'Ph.D. level', 'Engineering Manager level').
    - Identify key constraints: Citations required? Code examples required? Market data required?
    - If the user was vague, infer a high standard of professional quality.
    
    OUTPUT: A single, comprehensive paragraph defining the mission for the autonomous team.""",
    output_key="clarified_user_intent",
)

# --- INITIALIZER (Fix for KeyError) ---
# This agent runs once to set default values for variables used in the loop
class StateInitializerAgent(BaseAgent):
    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        # Initialize critique_result if it doesn't exist
        if "critique_result" not in context.session.state:
            context.session.state["critique_result"] = "No previous critique (First Draft)."
        yield Event(author=self.name, content=Content(parts=[Part(text="State initialized.")]))

# --- RESEARCH TEAM ---
tech_background_researcher = Agent(
    name="TechBackgroundResearcher",
    model=worker_model,
    instruction="""You are a Senior Technical Researcher.
    
    MISSION: Research the core theoretical and technical underpinnings of: {clarified_user_intent}.
    
    REQUIREMENTS:
    1. Do NOT provide surface-level definitions. Assume the reader is intelligent.
    2. Focus on architecture, algorithms, underlying physics/math, and system design.
    3. Identify controversies or debating points in the field.
    4. CITE YOUR SOURCES. Every claim must have a reference or origin.
    
    OUTPUT: A structured technical deep-dive.""",
    tools=[google_search],
    output_key="tech_background_research",
)

existing_solutions_researcher = Agent(
    name="ExistingSolutionsResearcher",
    model=worker_model,
    instruction="""You are a Market & Competitive Intelligence Analyst.
    
    MISSION: Analyze the landscape for: {clarified_user_intent}.
    
    REQUIREMENTS:
    1. Identify state-of-the-art (SOTA) solutions, competitors, or academic papers.
    2. Compare them critically. What are their tradeoffs? (Cost vs Performance, etc.)
    3. Look for recent developments (last 6-12 months).
    4. Provide specific metrics if available (benchmarks, market share, adoption rates).
    
    OUTPUT: A critical market analysis.""",
    tools=[google_search],
    output_key="existing_solutions_research",
)

tools_and_tech_researcher = Agent(
    name="ToolsAndTechResearcher",
    model=worker_model,
    instruction="""You are a Principal Software Architect.
    
    MISSION: Recommend the practical stack/tools for: {clarified_user_intent}.
    
    REQUIREMENTS:
    1. Do not just list tools; justify them based on the specific use case.
    2. Evaluate based on: Maturity, Community Support, Performance, and Ease of Use.
    3. Provide a 'Recommended Stack' vs 'Alternative Stack'.
    4. Mention any specific libraries or frameworks that are standard in the industry.
    
    OUTPUT: An architectural recommendation.""",
    tools=[google_search],
    output_key="tools_and_tech_research",
)

# --- WRITING & REFINEMENT ---
drafting_agent = Agent(
    name="DraftingAgent",
    model=worker_model,
    instruction="""You are a Technical Author for a top-tier industry publication (e.g., O'Reilly, Nature, HBR).
    
    INPUTS:
    - Directive: {clarified_user_intent}
    - Theory: {tech_background_research}
    - Market: {existing_solutions_research}
    - Tools: {tools_and_tech_research}
    - Feedback History: {critique_result}
    
    TASK: Synthesize these raw findings into a cohesive, narrative report.
    
    STYLE GUIDE:
    - Tone: Professional, Objective, Authoritative.
    - Structure: Executive Summary -> Technical Deep Dive -> Market Analysis -> Implementation Guide -> Conclusion.
    - **Crucial:** If you received Feedback ({critique_result}), you must specifically address those points in this rewrite.
    
    OUTPUT: The full report draft.""",
    output_key="report_draft",
)

dynamic_critic_agent = Agent(
    name="DynamicCriticAgent",
    model=critic_model,
    instruction="""You are an Executive Editor and Subject Matter Expert.
    
    TASK: Review the DRAFT ({report_draft}) against the DIRECTIVE ({clarified_user_intent}).
    
    CRITERIA:
    1. **Depth:** Is it too shallow? Does it explain 'how' and 'why', not just 'what'?
    2. **Accuracy:** Do the tools/market data make sense?
    3. **Completeness:** Did it answer the specific user focus?
    4. **Formatting:** Is it readable?
    
    DECISION:
    - If the report is excellent and ready for publication, output exactly: "APPROVED".
    - If it needs work, output a bulleted list of SPECIFIC, HIGH-IMPACT changes required. Be harsh but constructive.""",
    output_key="critique_result",
)

formatting_agent = Agent(
    name="FormattingAgent",
    model=critic_model,
    instruction="""You are a Layout Editor.
    
    TASK: Take the Approved Draft ({report_draft}) and apply final polish.
    1. Ensure a clear Main Title.
    2. Use H2 and H3 headers for structure.
    3. Use bullet points for readability where appropriate.
    4. Ensure code blocks are properly formatted (if any).
    5. Add a "References/Further Reading" section if sources were provided in the text.
    
    OUTPUT: The final Markdown document.""",
)

# --- GUARDRAILS ---
class SecurityGuardrailAgent(BaseAgent):
    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        intent = context.session.state.get("clarified_user_intent", "")
        if "hack" in intent.lower() or "exploit" in intent.lower():
            raise PermissionError("Security violation detected.")
        yield Event(author=self.name, content=Content(parts=[Part(text="Safe.")]))

class ReportValidationAgent(BaseAgent):
    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        critique = context.session.state.get("critique_result", "")
        if critique and "APPROVED" in critique.upper():
            yield Event(author=self.name, actions=EventActions(escalate=True), content=Content(parts=[Part(text="Approved")]))
        else:
            yield Event(author=self.name, content=Content(parts=[Part(text="Revising")]))