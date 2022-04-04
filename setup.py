from setuptools import setup


setup(
    name="argclass",
    version="0.4.1",
    platforms="all",
    author="Dmitry Orlov",
    author_email="me@mosquito.su",
    maintainer="Dmitry Orlov",
    maintainer_email="me@mosquito.su",
    description=(
        "A wrapper around the standard argparse module that allows "
        "you to describe argument parsers declaratively."
    ),
    package_dir={"": "src"},
    packages=[],
    license="Apache 2",
    long_description=open("README.rst").read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
