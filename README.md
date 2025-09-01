
## Development Workflow

1. **Development Phase**: Work directly in the `app/` directory, run `app/main.py` from your IDE
2. **Performance Optimization**: Move critical code to `cython_logic/` and set `COMPILE_CYTHON = True`
3. **Testing Distribution**: Set `BUILD_EXECUTABLE = True` to create standalone executable
4. **Production Release**: Enable all flags to create professional installer package

## Requirements

- Python 3.11+
- PyCharm (recommended) or any Python IDE
- Windows (for MSI installer creation)

The template handles all the complexity of Cython compilation, PyInstaller packaging, and installer creation through a single, configurable build script.

