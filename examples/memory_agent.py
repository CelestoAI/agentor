from agents import Runner
from zerozen.utils import AppContext, CoreServices
from zerozen.memory.api import Memory
from zerozen.agenthub.memagent import build_memory_agent

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
