def test_package_import_and_version():
    import ai_runtime_experiments  # pyright: ignore[reportMissingImports]

    assert ai_runtime_experiments.__version__ == "0.1.0"
