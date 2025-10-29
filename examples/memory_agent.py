from agents import Runner

from agentor.agenthub.memagent import build_memory_agent
from agentor.memory.api import Memory
from agentor.utils import AppContext, CoreServices

agent = build_memory_agent()
mem = Memory()
runner = Runner()
output = runner.run_sync(
    agent,
    "What is the capital of France?",
    context=AppContext(core=CoreServices(memory=mem)),
)
print(output)

print(mem.get_full_conversation())
