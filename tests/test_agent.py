# In tests/test_agent.py

import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

# We only need to import our single entry point: the root_agent.
from research_agent import root_agent

async def main():
    """
    This script confirms that the full agent application and all its components
    can be loaded correctly without import errors. The full interactive workflow
    should be tested using the 'adk web' command.
    """
    print("Attempting to initialize the agent and its services...")
    
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    
    # This will fail if there are any circular dependencies or import errors.
    runner = Runner(
        agent=root_agent,
        app_name="research_app",
        session_service=session_service,
        memory_service=memory_service,
    )
    
    print("\n" + "="*60)
    print("✅ SUCCESS: Project structure and imports are correct.")
    print("✅ The 'root_agent' (ResearchConcierge) has been successfully loaded.")
    print("\nNext Step: Run 'adk web' in your terminal to interact with the agent.")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())