from setuptools import setup, find_packages

setup(
    name="selfhost-cli",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "click",
        "boto3",
        "rich"
    ],
    entry_points={
        "console_scripts": [
            "selfhost-cli=selfhost_cli.cli:cli"
        ],
    },
)