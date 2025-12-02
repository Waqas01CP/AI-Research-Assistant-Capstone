from google.adk.tools import ToolContext
from google.adk.runners import Runner
from google.adk.events import Event
from google.genai.types import Content, Part
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

async def run_research_pipeline(tool_context: ToolContext, topic: str, specific_focus: str, audience: str) -> dict:
    """
    Executes the autonomous research pipeline in an isolated environment.
    
    ARCHITECTURAL Note:
    This function implements the "Session Isolation" pattern. 
    Problem: Multi-agent research generates massive amounts of raw data (search results, 
    internal drafts, critique logs) which would pollute the user's main chat context window.
    
    Solution: We instantiate a fresh `InMemorySessionService` here. This creates a 
    temporary, private workspace for the sub-agents. They do their messy work in private, 
    and only the final polished report is returned to the main user session.
    """
    
    # Local imports to prevent circular dependencies at the module level
    from .agent import autonomous_pipeline
    from .internal_agents import intent_synthesis_agent

    # 1. Setup Isolated Environment (The Private Workspace)
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    
    # We create a derived session ID to track this specific job logically
    internal_id = f"research-{tool_context._invocation_context.session.id}"
    user_id = tool_context._invocation_context.session.user_id
    
    # Initialize the private session
    await session_service.create_session(app_name="research_agent", user_id=user_id, session_id=internal_id)

    # 2. Run Synthesis Phase
    # The first step is to combine the chat arguments into a robust prompt for the researchers.
    runner = Runner(
        agent=intent_synthesis_agent, app_name="research_agent",
        session_service=session_service, memory_service=memory_service
    )
    
    # We construct the input from the arguments passed by the Root Agent
    synthesis_input = f"""
    Topic: {topic}
    Specific Focus: {specific_focus}
    Target Audience: {audience}
    """
    
    msg = Content(role="user", parts=[Part(text=synthesis_input)])
    async for event in runner.run_async(session_id=internal_id, user_id=user_id, new_message=msg): pass 

    # 3. Run the Autonomous Pipeline
    # This triggers the Sequential Agent (Security -> Parallel Research -> Refinement Loop)
    runner = Runner(
        agent=autonomous_pipeline, app_name="research_agent",
        session_service=session_service, memory_service=memory_service
    )
    
    # The pipeline is self-driven based on session state, but needs a trigger event to start.
    trigger_msg = Content(role="user", parts=[Part(text="Begin Research Pipeline")])
    
    final_report = "Report generation failed."
    # Added new_message=trigger_msg here
    async for event in runner.run_async(session_id=internal_id, user_id=user_id, new_message=trigger_msg):
            if event.is_final_response() and event.content and event.content.parts:
                final_report = event.content.parts[0].text
    
    return {"status": "success", "report": final_report}