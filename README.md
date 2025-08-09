<center>

<div align="center">

<img src="/assets/zerozen-min.png" alt="zerozen" width="200" />

<br>

# Your hyper-personal, always-on, open-source AI companion.

Dedicated to the [creators of Zero](https://www.open.ac.uk/blogs/MathEd/index.php/2022/08/25/the-men-who-invented-zero/) — Aryabhatta and Bhaskara ✨

<img src="/assets/cli.png" alt="zerozen CLI" width="500" />

</div>

</center>

______________________________________________________________________

## Table of Contents

- [Installation](#installation)

- [Usage](#usage)

  - [Convert Pydantic Models to XML](#convert-pydantic-models-to-xml)
  - [Chat Interface](#chat-interface)
  - [Gmail Search Tool](#gmail-search-tool)

- [Roadmap](#roadmap)

- [Contributing](#contributing)

______________________________________________________________________

## Installation

```bash
pip install zenzero
```

### Install from source

```bash
pip install git+https://github.com/aniketmaurya/zerozen.git
```

______________________________________________________________________

## Usage

### Convert Pydantic Models to XML

```python
from zerozen import pydantic_to_xml
from pydantic import BaseModel


class User(BaseModel):
    name: str
    age: int


user = User(name="John", age=30)
xml_string = pydantic_to_xml(user)
print(xml_string)
```

**Output:**

```xml
<User><name>John</name><age>30</age></User>
```

______________________________________________________________________

### Chat Interface

```bash
zen chat
```

______________________________________________________________________

### Gmail Search Tool

Now integrated with a Gmail search feature via OpenAI Agents.

#### Setup

1. Place `credentials.json` (OAuth credentials) in the project root.
1. Run this tool to set up Gmail search for your agent:

```bash
zen setup-gmail
```

#### Example usage in Python:

```python
from zerozen import agents

prompt = "Find emails from Stripe with invoices in the last 7 days."

result = agents.run_sync(
    prompt,
    tools=["search_gmail"],
    user_context={"email_user_id": "me"},
)
print(result)
```

- The agent uses `search_gmail` to locate matching emails and returns snippets like sender, subject, date, and snippet.
- The search tool works out-of-the-box once authenticated and ready.
- Perfect for building more sophisticated workflows—replying, summarization, reaction automation, and more.

______________________________________________________________________

## Roadmap

| Feature                                      | Status     |
| -------------------------------------------- | ---------- |
| Pydantic-to-XML                              | ✅          |
| CLI Chat Interface                           | ✅          |
| Gmail Integration (search)                   | ✅          |
| Gmail Agent: Read, Draft, Reply              | 🔳 Planned |
| “Review & Send” workflow                     | 🔳 Planned |
| Multi-tool Agents (email, calendar, docs...) | 🔳 Planned |

______________________________________________________________________

## Contributing

Contributions are welcome! We recommend:

- Opening an issue to suggest features or report bugs
- Submitting pull requests with clear descriptions and tests

______________________________________________________________________

Enjoy the **Zen** of zero-friction AI tooling!
