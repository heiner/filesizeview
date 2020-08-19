import setuptools


def main():
    with open("README.md", "r") as fh:
        long_description = fh.read()

    setuptools.setup(
        name="filesizeview",
        version="0.0.3",
        description="Graphical display of file sizes on terminal",
        long_description=long_description,
        long_description_content_type="text/markdown",
        entry_points={"console_scripts": ["filesizeview = filesizeview.py",]},
        packages=[],
        url="https://github.com/heiner/filesizeview",
        python_requires=">=3.0",
    )


if __name__ == "__main__":
    main()
