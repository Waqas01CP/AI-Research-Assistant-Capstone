from google.adk.agents import Agent, BaseAgent
from google.adk.tools import google_search
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
from typing import AsyncGenerator
from .config import worker_model, critic_model

# =============================================================================
# PHASE 1: CONTEXT ENGINEERING & SYNTHESIS
# Design Pattern: "Context Compaction"
# =============================================================================
# The user's chat history might be messy. This agent acts as a "Compressor".
# It takes the back-and-forth conversation and distills it into a single,
# high-fidelity directive. This ensures the research agents don't get distracted
# by conversational filler.

intent_synthesis_agent = Agent(
    name="IntentSynthesisAgent",
    model=critic_model, # Using the smarter 'Pro' model for reasoning
    instruction="""You are a Lead Research Architect.
    
    ### INPUT DATA
    You will receive a conversation history containing:
    1. The User's initial vague topic.
    2. The User's specific answers regarding Focus, Audience, and Depth.
    
    ### YOUR MISSION
    Synthesize this information into a 'Master Research Directive'.
    
    ### CONSTRAINTS
    - Do not summarize the chat. Create an instruction manual for a research team.
    - Explicitly state the technical depth required (e.g., "Ph.D. level" vs "High School level").
    - If the user was vague, infer a high standard of professional quality.
    
    ### OUTPUT FORMAT
    A single, dense paragraph starting with: "RESEARCH DIRECTIVE: ..."
    """,
    output_key="clarified_user_intent", # Saves result to session state
)

# --- INITIALIZER (Fix for KeyError) ---
# This agent runs once to set default values for variables used in the loop
class StateInitializerAgent(BaseAgent):
    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        # Initialize critique_result if it doesn't exist
        if "critique_result" not in context.session.state:
            context.session.state["critique_result"] = "No previous critique (First Draft)."
        yield Event(author=self.name, content=Content(parts=[Part(text="State initialized.")]))


# =============================================================================
# PHASE 2: PARALLEL RESEARCH TEAM
# Design Pattern: "Parallel Execution"
# =============================================================================
# Instead of one agent doing everything sequentially (slow), we spawn three
# specialist agents to run simultaneously. This reduces latency and ensures
# diverse perspectives (Theoretical, Market, and Practical).

tech_background_researcher = Agent(
    name="TechBackgroundResearcher",
    model=worker_model,
    instruction="""You are a Senior Technical Researcher.
    
    ### MISSION
    Research the core theoretical and technical underpinnings of: {clarified_user_intent}.
    
    ### EXECUTION RULES
    1. **Depth over Breadth:** Do NOT provide surface-level definitions. Assume the reader is intelligent.
    2. **Technical Focus:** Focus on architecture, algorithms, underlying physics/math, and system design.
    3. **Academic Rigor:** Identify controversies or debating points in the field.
    4. **Citations:** Use the google_search tool to find real sources.
    """,
    tools=[google_search],
    output_key="tech_background_research",
)

existing_solutions_researcher = Agent(
    name="ExistingSolutionsResearcher",
    model=worker_model,
    instruction="""You are a Market & Competitive Intelligence Analyst.
    
    ### MISSION: Analyze the landscape for: {clarified_user_intent}.
    
    ### EXECUTION RULES:
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
    
    ### MISSION: Recommend the practical stack/tools for: {clarified_user_intent}.
    
    ### EXECUTION RULES:
    1. Do not just list tools; justify them based on the specific use case.
    2. Evaluate based on: Maturity, Community Support, Performance, and Ease of Use.
    3. Provide a 'Recommended Stack' vs 'Alternative Stack'.
    4. Mention any specific libraries or frameworks that are standard in the industry.
    
    OUTPUT: An architectural recommendation.""",
    tools=[google_search],
    output_key="tools_and_tech_research",
)

# =============================================================================
# PHASE 3: REFINEMENT LOOP (Draft -> Critique -> Validate)
# Design Pattern: "Iterative Refinement / Loop"
# =============================================================================
# This is a self-correcting mechanism. The system will not output the first draft.
# It forces a critique cycle to improve quality before the user ever sees it.

drafting_agent = Agent(
    name="DraftingAgent",
    model=worker_model,
    instruction="""You are a Technical Author for a top-tier industry publication (e.g., O'Reilly, Nature, HBR).
    
    ### INPUT CONTEXT
    - Directive: {clarified_user_intent}
    - Theoretical Data: {tech_background_research}
    - Market Data: {existing_solutions_research}
    - Practical Data: {tools_and_tech_research}
    - **CRITIC FEEDBACK:** {critique_result}
    
    ### TASK: Synthesize these raw findings into a cohesive, narrative report.
    
    ### STYLE GUIDE:
    - Tone: Professional, Objective, Authoritative.
    - Structure: Provide a better structure than the given below and if unable to do it then use the given below:
        "Executive Summary -> Technical Deep Dive -> Market Analysis -> Implementation Guide -> Conclusion."
    
    ### CRITICAL INSTRUCTION:
    - **Crucial:** If you received Feedback ({critique_result}), you must specifically address those points in this rewrite.
    - Do not ignore the critic.
    
    OUTPUT: The full report draft.""",
    output_key="report_draft",
)

dynamic_critic_agent = Agent(
    name="DynamicCriticAgent",
    model=critic_model,
    instruction="""You are an Executive Editor and Subject Matter Expert.
    
    ### TASK: Review the DRAFT ({report_draft}) against the DIRECTIVE ({clarified_user_intent}).
    
    ### CRITERIA:
    1. **Depth:** Is it too shallow? Does it explain 'how' and 'why', not just 'what'? 
    2. **Accuracy:** Do the tools/market data make sense?
    3. **Completeness:** Did it answer the specific user focus?
    4. **Formatting:** Is it readable?
    
    ### DECISION:
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

# =============================================================================
# PHASE 4: DETERMINISTIC GUARDRAILS
# Design Pattern: "Keyword Filtering"
# =============================================================================

class SecurityGuardrailAgent(BaseAgent):
    """
    Acts as a firewall. Checks for malicious keywords before allowing
    the agents to access the internet tools.
    """
    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        # 1. Get the intent
        intent = context.session.state.get("clarified_user_intent", "")
        
        # 2. Define Forbidden Concepts (Expanded list)
        forbidden_keywords = [
            "hack", "exploit", "malware", "illegal", "bypass", 
            "phishing", "ddos", "keylogger", "ransomware", 
            "bomb", "weapon", "steal", "fraud"
        ]
        
        # 3. Check (Case-insensitive)
        print(f"\n🛡️ [Security Guardrail] Scanning intent: '{intent}'")
        
        found_violation = False
        for bad_word in forbidden_keywords:
            if bad_word in intent.lower():
                found_violation = True
                print(f"🚨 [Security Guardrail] BLOCKED. Keyword found: '{bad_word}'")
                break
        
        if found_violation:
            # This specific error text comes from YOUR code, not Gemini.
            raise PermissionError("Security Violation: Request denied by local policy (Keyword Filter).")
        
        print("✅ [Security Guardrail] PASSED.")
        yield Event(author=self.name, content=Content(parts=[Part(text="Security Check Passed.")]))

class ReportValidationAgent(BaseAgent):
    """
    Acts as the Logic Gate for the Refinement Loop.
    It reads the Critic's output string. If it sees "APPROVED", it triggers
    the 'escalate' action to break the loop. Otherwise, it lets the loop continue.
    """
    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        critique = context.session.state.get("critique_result", "")
        if critique and "APPROVED" in critique.upper():
            yield Event(author=self.name, actions=EventActions(escalate=True), content=Content(parts=[Part(text="Approved")]))
        else:
            yield Event(author=self.name, content=Content(parts=[Part(text="Revising")]))