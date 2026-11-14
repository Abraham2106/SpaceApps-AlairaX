"""Smoke test: el paquete `app` se instala y sus módulos base importan.

No valida física todavía; solo que la estructura del repo está sana.
"""


def test_package_layout_imports() -> None:
    import app  # noqa: F401
    import app.api  # noqa: F401
    import app.application  # noqa: F401
    import app.domain  # noqa: F401
    import app.infrastructure  # noqa: F401
    import app.intelligence  # noqa: F401
    import app.simulation  # noqa: F401
