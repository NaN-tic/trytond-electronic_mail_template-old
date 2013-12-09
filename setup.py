#!/usr/bin/env python
#This file is part electronic_mail_template module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
"Setup Electronic Mail Template"

from setuptools import setup
import re
import ConfigParser

config = ConfigParser.ConfigParser()
config.readfp(open('tryton.cfg'))
info = dict(config.items('tryton'))
for key in ('depends', 'extras_depend', 'xml'):
    if key in info:
        info[key] = info[key].strip().splitlines()
major_version, minor_version, _ = info.get('version', '0.0.1').split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

requires = []
for dep in info.get('depends', []):
    if not re.match(r'(ir|res|workflow|webdav)(\W|$)', dep):
        requires.append('trytond_%s >= %s.%s, < %s.%s' %
                (dep, major_version, minor_version, major_version,
                    minor_version + 1))
requires.append('trytond >= %s.%s, < %s.%s' %
        (major_version, minor_version, major_version, minor_version + 1))

setup(name='trytonzz_electronic_mail_template',
    version=info.get('version', '0.0.1'),
    description='Electronic mail storage',
    author='Openlabs Technologies & Consulting (P) LTD',
    author_email='info@openlabs.co.in',
    url='http://openlabs.co.in/',
    download_url='https://bitbucket.org/zikzakmedia/trytond-electronic_mail',
    package_dir={'trytond.modules.electronic_mail_template': '.'},
    packages=[
        'trytond.modules.electronic_mail_template',
        'trytond.modules.electronic_mail_template.tests',
    ],
    package_data={
        'trytond.modules.electronic_mail_template': info.get('xml', []) \
            + ['tryton.cfg', 'view/*.xml', 'locale/*.po'],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Framework :: Tryton',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Legal Industry',
        'Intended Audience :: Manufacturing',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Office/Business',
    ],
    license='GPL-3',
    install_requires=requires,
    zip_safe=False,
    entry_points="""
    [trytond.modules]
    electronic_mail = trytond.modules.electronic_mail_template
    """,
    test_suite='tests',
    test_loader='trytond.test_loader:Loader',
)
