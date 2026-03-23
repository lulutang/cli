# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="safeskill-cli",
    version="1.1.0",
    description="SafeSkill CLI — Skill 安全扫描命令行工具",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="QAX Threat Intelligence",
    author_email="ti_support@qianxin.com",
    url="https://safeskill.qianxin.com/",
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "requests>=2.20",
        "pyyaml>=5.0",
    ],
    entry_points={
        "console_scripts": [
            "safeskill=safeskill.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
    ],
)
