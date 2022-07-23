from setuptools import setup, find_packages
from syncronizer import __version__


with open("README.md", "r") as f:
    long_description = f.read()

with open("requirements.txt", "r") as f:
    install_requires = f.read().split("\n")

setup(
    name='syncronizer',
    version=__version__,
    author='Timur Fattakhov',
    author_email='timur.fattahov1996@gmail.com',
    long_description=long_description,
    description="Syncronizator",
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    zip_safe=False,
    python_requires="==3.8.*",
    # entry_points={
    #     "airflow.plugins": [
    #         "nextstage = nextstage.plugin:NextstagePlugin"
    #     ],
    #     'console_scripts': ['nextstage=nextstage.cli.main:main'],
    # },
)

# python setup.py sdist bdist_wheel