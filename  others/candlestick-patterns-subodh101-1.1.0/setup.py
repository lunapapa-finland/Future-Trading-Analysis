#!/usr/bin/env python
from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="candlestick-patterns-subodh101",
    version="1.1.0",
    author="Subodh Pushkar",
    author_email="subodh.pushkar@gmail.com",
    description="A trading candlestick pattern package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/subodh101/candlestick-patterns-subodh101",
    packages=find_packages(),
    package_data={"candlestick": ["py.typed"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
