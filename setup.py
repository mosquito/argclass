from setuptools import setup


setup(
    name='argclass',
    version='0.1.0',
    platforms="all",
    author="Dmitry Orlov",
    author_email="me@mosquito.su",
    maintainer="Dmitry Orlov",
    maintainer_email="me@mosquito.su",
    description="Declarative argparse definition",
    package_dir={'': 'src'},
    packages=[''],
    license="Apache 2",
    long_description=open('README.rst').read(),
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
    ],
)
