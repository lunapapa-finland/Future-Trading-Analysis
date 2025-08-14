# setup.py
from setuptools import find_packages, setup

def read_requirements():
    with open("requirements.txt", encoding="utf-8") as f:
        reqs = []
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            reqs.append(ln)
        return reqs

setup(
    name="dashboard",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    author="Lunapapa",
    license="MIT",
    install_requires=read_requirements(),
    include_package_data=True,     # include non-.py files in packages
)
