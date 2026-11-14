"""Smoke test: el paquete `backend.app` (ejecutado desde la raíz) sus módulos base importan.

No valida física todavía; solo que la estructura del repo está sana.
"""


def test_package_layout_imports() -> None:
    import backend.app  # noqa: F401
    import backend.app.api  # noqa: F401
    import backend.app.application  # noqa: F401
    import backend.app.domain  # noqa: F401
    import backend.app.infrastructure  # noqa: F401
    import backend.app.intelligence  # noqa: F401
    import backend.app.simulation  # noqa: F401
