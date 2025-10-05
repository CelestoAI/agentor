from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from pydantic import BaseModel


def pydantic_to_xml(obj: BaseModel) -> str:
    def value_to_xml(parent: Element, key: str, value: Any):
        if isinstance(value, BaseModel):
            child = SubElement(parent, key)
            model_to_xml(child, value)
        elif isinstance(value, dict):
            child = SubElement(parent, key)
            for k, v in value.items():
                value_to_xml(child, k, v)
        elif isinstance(value, list):
            for item in value:
                value_to_xml(parent, key, item)
        else:
            child = SubElement(parent, key)
            child.text = str(value)

    def model_to_xml(parent: Element, model: BaseModel):
        model_dict = model.model_dump()
        for key, value in model_dict.items():
            value_to_xml(parent, key, value)

    root = Element(obj.__class__.__name__)
    model_to_xml(root, obj)
    return tostring(root, "utf-8").decode()
