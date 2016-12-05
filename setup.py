from setuptools import setup

setup(
    name='asyncbb',
    version='0.0.1',
    author='Tristan King',
    author_email='tristan.king@gmail.com',
    packages=['asyncbb', 'asyncbb.test'],
    url='http://github.com/tristan/asyncbb',
    description='Basic service setup using tornado and asyncpg',
    long_description=open('README.md').read(),
    install_requires=[
        'tornado==4.4.2'
    ],
    setup_requires=['pytest-runner'],
    tests_require=[
        'pytest',
        'testing.postgresql==1.3.0',
        'asyncpg==0.7.0',
        'redis==2.10.5'
    ]
)
