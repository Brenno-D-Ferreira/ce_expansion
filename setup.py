import setuptools

# read in version of canela package
v = {}
with open('ce_expansion/_version.py', 'r') as fid:
    # this will create the __version__ variable to be used below
    exec(fid.read(), v)

with open("README.md", "r") as readme:
    long_description = readme.read()

setuptools.setup(name="ce_expansion",
                 version=v["__version__"],
                 author="CANELa",
                 author_email="gmpourmp@pitt.edu",
                 description="Global optimization of ground-state NP chemical ordering",
                 long_description=long_description,
                 long_description_content_type="text/markdown",
                 url="https://github.com/mpourmpakis/ce_expansion",
                 project_urls={"Source": "https://github.com/mpourmpakis/ce_expansion",
                               "Funding": "https://nsf.gov/",
                               "CANELa Group": "https://mpourmpakis.com/",
                               "Institution": "https://pitt.edu", },
                 license="MIT",
                 platforms=["Windows", "Unix"],
                 packages=setuptools.find_packages(),
                 include_package_data=True,
                 keywords="chemistry computational_chemistry nanoparticles chemical_ordering cohesive_energy atomgraph",
                 classifiers=["Development Status :: 4 - Beta",
                              "Environment :: Console",
                              "Intended Audience :: Education",
                              "Intended Audience :: Science/Research",
                              "License :: OSI Approved :: MIT License",
                              "Operating System :: Microsoft :: Windows",
                              "Operating System :: Unix",
                              "Programming Language :: C",
                              "Programming Language :: Python :: 2.7"
                              "Programming Language :: Python :: 3",
                              "Topic :: Scientific/Engineering",
                              "Topic :: Scientific/Engineering :: Chemistry",
                              "Topic :: Scientific/Engineering :: Physics",
                              "Topic :: Scientific/Engineering :: Visualization"],
                 python_requires=">=3.7",
                 install_requires=["ase>=3.18.1", "numpy", "matplotlib", "seaborn", "sqlalchemy"],
                 zip_safe=False)
