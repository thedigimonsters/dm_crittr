from setuptools import setup
from Cython.Build import cythonize

setup(
    name="secure_logic",
    ext_modules=cythonize("secure_logic.pyx", compiler_directives={"language_level": "3"}),
)
