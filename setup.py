from setuptools import setup

setup(
    name='src',
    packages=['src'],
    version='1.0',
    description='Official code for generate human face.',
    author='Team 64',
    package_data = {'src': ['stylegan3/**/*']}
)
