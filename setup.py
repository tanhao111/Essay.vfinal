from setuptools import setup

setup(
    name='src',
    packages=['src'],
    version='1.0',
    description='Official code for generate human face.',
    author='Justin Pinkney',
    package_data = {'src': ['stylegan3/**/*']}
)
