from setuptools import setup

with open("README.md") as f:
    long_description = f.read()

setup(
    name='better_feediverse',
    version='2.0.2',
    python_requires='>=3.3',
    url='https://github.com/xopez/better_feediverse',
    author='Ed Summers, Xopez',
    author_email='28950736+xopez@users.noreply.github.com',
    py_modules=['better_feediverse'],
    description='Connect an RSS Feed to Mastodon',
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=['beautifulsoup4',
                      'feedparser',
                      'mastodon.py',
                      'python-dateutil',
                      'pyyaml'],
    entry_points={'console_scripts': ['better_feediverse = better_feediverse:main']}
)
