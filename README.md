# zerozen

![zerozen.png](zerozen.png)

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
