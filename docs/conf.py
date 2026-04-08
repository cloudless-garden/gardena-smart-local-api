import importlib.metadata

project = "gardena-smart-local-api"
copyright = "cloudless-garden contributors"
author = "cloudless-garden"
release = importlib.metadata.version("gardena-smart-local-api")

extensions = [
    "autoapi.extension",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
]

html_theme = "pydata_sphinx_theme"
html_title = "gardena-smart-local-api"

autoapi_dirs = ["../gardena_smart_local_api"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]
autoapi_ignore = ["*/examples/*", "*/schema/*"]
autoapi_python_class_content = "both"

napoleon_google_docstring = True
napoleon_numpy_docstring = False
