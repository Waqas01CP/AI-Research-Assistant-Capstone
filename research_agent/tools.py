from google.adk.tools import ToolContext
from google.adk.runners import Runner
from google.adk.events import Event
from google.genai.types import Content, Part
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

async def run_research_pipeline(tool_context: ToolContext, topic: str, specific_focus: str, audience: str) -> dict:
    """
    Executes the autonomous research pipeline.
    ONLY call this after you have gathered the topic, focus, and audience from the user.
    """
    
    # Imports
    from .agent import autonomous_pipeline
    from .internal_agents import intent_synthesis_agent

    # Setup isolated environment
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    
    internal_id = f"research-{tool_context._invocation_context.session.id}"
    user_id = tool_context._invocation_context.session.user_id

    await session_service.create_session(app_name="research_agent", user_id=user_id, session_id=internal_id)

    # 1. Run Synthesis (Combine the args into a plan)
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

    # 2. Run the Autonomous Pipeline
    runner = Runner(
        agent=autonomous_pipeline, app_name="research_agent",
        session_service=session_service, memory_service=memory_service
    )
    
    # CRITICAL FIX: The pipeline needs a 'kickoff' message to start running.
    # It won't use the text content (it reads from session state), but it needs the event.
    trigger_msg = Content(role="user", parts=[Part(text="Begin Research Pipeline")])
    
    final_report = "Report generation failed."
    # Added new_message=trigger_msg here
    async for event in runner.run_async(session_id=internal_id, user_id=user_id, new_message=trigger_msg):
            if event.is_final_response() and event.content and event.content.parts:
                final_report = event.content.parts[0].text
    
    return {"status": "success", "report": final_report}