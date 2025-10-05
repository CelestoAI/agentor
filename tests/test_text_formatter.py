from agentor import pydantic_to_xml
from pydantic import BaseModel


class Address(BaseModel):
    street: str
    city: str


class User(BaseModel):
    name: str
    age: int
    address: Address


def test_output_text_formatter():
    user_instance = User(
        name="John", age=30, address=Address(street="123 Elm St", city="Springfield")
    )
    xml_string = pydantic_to_xml(user_instance)
    assert (
        xml_string
        == """<User><name>John</name><age>30</age><address><street>123 Elm St</street><city>Springfield</city></address></User>"""
    )


if __name__ == "__main__":
    test_output_text_formatter()
