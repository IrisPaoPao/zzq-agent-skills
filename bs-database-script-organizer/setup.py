from setuptools import setup, find_packages

setup(
    name="bsq-sql-organize",
    version="1.1.1",
    description="Organize and archive saas-database migration scripts (replacing 数据库脚本工具.exe)",
    author="张政卿",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "bsq-sql-organize = bs_database_script_organizer.cli:main",
            "bs-sql-organize = bs_database_script_organizer.cli:main",
        ],
    },
    python_requires=">=3.8",
)
