"""
curl -X 'POST' \
  'http://localhost:8000/chat' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "What is the weather in London?"
}'
"""

from agentor import Agentor

agent = Agentor(
    name="Agentor",
    model="gpt-5-mini",
    tools=["get_weather"],
)


agent.serve(port=8000)
