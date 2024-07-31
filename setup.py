#!/usr/bin/env python3

"Setuptools params"

from setuptools import setup, find_packages
from os.path import join

# Get version number from source tree
#import sys
#sys.path.append( '.' )
VERSION = "0.1.0"

scripts = [ join( 'bin', filename ) for filename in [ 'mnsec', 'mnsecx' ] ]

modname = distname = 'mininet-sec'

with open("requirements.txt", "r", encoding="utf8") as file:
    install_requires = [line.strip() for line in file
                        if not line.startswith("#")]


setup(
    name=distname,
    version=VERSION,
    description='Emulation platform for cybersecurity tools in programmable networks',
    author='Italo Valcy',
    author_email='italovalcy@ufba.br',
    long_description="""
        Mininet-Sec is a network emulator platform for studying and
        experimenting cybersecurity tools in programmable networks.
        """,
    classifiers=[
          "License :: OSI Approved :: BSD License",
          "Programming Language :: Python",
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "Topic :: System :: Emulators",
          "Topic :: Security",
    ],
    keywords='networking emulator cybersecurity',
    license='BSD',
    install_requires=install_requires,
    scripts=scripts,
    package_data={"mnsec.assets": ["*"],"mnsec.templates": ["*"]},
)
