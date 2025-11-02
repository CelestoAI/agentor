from .core import app
from .a2a import app as a2a_app

app.add_typer(a2a_app, name="a2a")

__all__ = ["app"]
