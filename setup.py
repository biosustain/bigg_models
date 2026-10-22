import sys
from os.path import join, dirname, abspath

from setuptools import setup, find_packages

# this is a trick to get the version before the package is installed
directory = dirname(abspath(__file__))
sys.path.insert(0, join(directory, "biggr_models"))
version = __import__("version").__version__

setup(
    name="biggr_models",
    version=version,
    author="Pascal Pieters",
    author_email="paspie@biosustain.dtu.dk",
    url="http://bigg.ucsd.edu",
    packages=find_packages(),
    package_data={
        "biggr_models": [
            "static/assets/*",
            "static/css/*",
            "static/js/*",
            "templates/*",
            "db_management/*",
        ]
    },
    license="Apache-2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
    install_requires=[
        "cobradb",
        "Jinja2",
    ],
)
