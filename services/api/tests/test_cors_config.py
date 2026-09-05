from app.main import _cors_origins


def test_cors_origins_include_local_development_defaults() -> None:
    origins = _cors_origins("")

    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3001" in origins


def test_cors_origins_add_deployed_frontends_without_trailing_slashes() -> None:
    origins = _cors_origins(
        " https://breakpoint.example.com/, https://preview.example.com "
    )

    assert "https://breakpoint.example.com" in origins
    assert "https://preview.example.com" in origins


def test_cors_origins_are_deduplicated() -> None:
    origins = _cors_origins("http://localhost:3000, https://breakpoint.example.com")

    assert origins.count("http://localhost:3000") == 1
