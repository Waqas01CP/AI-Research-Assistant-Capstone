from google.adk.agents import Agent, SequentialAgent, ParallelAgent, LoopAgent
from google.adk.tools import FunctionTool
from .config import worker_model
from .internal_agents import (
    StateInitializerAgent, # <--- Added Import
    SecurityGuardrailAgent, tech_background_researcher, existing_solutions_researcher,
    tools_and_tech_researcher, drafting_agent, dynamic_critic_agent,
    ReportValidationAgent, formatting_agent
)
from .tools import run_research_pipeline

# =============================================================================
# THE AUTONOMOUS PIPELINE
# =============================================================================
# This is a SequentialAgent that acts as the backbone of the system.
# It forces a strict order of operations: Safety First -> Research -> Refine.

autonomous_pipeline = SequentialAgent(
    name="AutonomousPipeline",
    sub_agents=[
        StateInitializerAgent(name="Initializer"), 
        # Step 1: Deterministic Security Check
        SecurityGuardrailAgent(name="SecurityGuardrail"),

        # Step 2: Parallel Research
        # (Runs 3 agents concurrently to maximize efficiency)
        ParallelAgent(
            name="ResearchTeam", 
            sub_agents=[tech_background_researcher, existing_solutions_researcher, tools_and_tech_researcher]
        ),

        # Step 3: The Refinement Loop
        # (Cycles until quality standards are met or max_iterations reached)
        LoopAgent(
            name="RefinementCycle",
            sub_agents=[drafting_agent, dynamic_critic_agent, ReportValidationAgent(name="ReportValidator")],
            max_iterations=3, 
        ),

        # Step 4: Final Formatting
        formatting_agent,
    ],
)

# =============================================================================
# THE ROOT AGENT (Chat Interface)
# =============================================================================
# This agent handles the user interaction. Its primary job is Requirement Gathering.
# It effectively acts as a router, deciding when enough information is present
# to dispatch the expensive 'run_research_pipeline' tool.

root_agent = Agent(
    name="ResearchConcierge",
    model=worker_model,
    instruction="""You are a Research Concierge.
    
    YOUR PROCESS:
    1. When a user asks for research, do NOT call the tool immediately.
    2. You must first ask clarifying questions in the chat to understand:
       - The Specific Focus (what exactly to look for)
       - The Target Audience (who is this for?)
    
    3. ONLY after the user answers these questions in the chat, call the `run_research_pipeline` tool.
    4. Pass the user's answers into the tool arguments.
    """,
    tools=[FunctionTool(func=run_research_pipeline)],
)