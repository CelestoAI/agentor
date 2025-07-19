<center>

<div align="center">

<img src="/assets/zerozen-min.png" alt="zerozen" width="200" />

<br>

# LLMs in Zen Mode

Dedicated to the [creators of Zero](https://www.open.ac.uk/blogs/MathEd/index.php/2022/08/25/the-men-who-invented-zero/) - Aryabhatta and Bhaskara ✨

<img src="/assets/cli.png" alt="zerozen" width="500" />

</div>

</center>

# Installation

```bash
uv pip install git+https://github.com/aniketmaurya/zerozen.git
```

# Usage

## Convert Pydantic models to XML

```python
from zerozen import pydantic_to_xml


class User(BaseModel):
    name: str
    age: int


user_instance = User(name="John", age=30)
xml_string = pydantic_to_xml(user_instance)
print(xml_string)
```

**Output:**

```xml
<User><name>John</name><age>30</age></User>
```

## Chat

```bash
zerozen chat
```

## Coming up - Claude code like agents
