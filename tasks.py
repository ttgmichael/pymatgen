# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import glob
import os
import json
import webbrowser
import requests
import re
import subprocess
import datetime
from invoke import task

from monty.os import cd
from pymatgen import __version__ as CURRENT_VER

NEW_VER = datetime.datetime.today().strftime("%Y.%-m.%-d")


"""
Deployment file to facilitate releases of pymatgen.
Note that this file is meant to be run from the root directory of the pymatgen
repo.
"""

__author__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "Sep 1, 2014"


@task
def make_doc(ctx):
    with open("CHANGES.rst") as f:
        contents = f.read()

    toks = re.split("\-{3,}", contents)
    n = len(toks[0].split()[-1])
    changes = [toks[0]]
    changes.append("\n" + "\n".join(toks[1].strip().split("\n")[0:-1]))
    changes = ("-" * n).join(changes)

    with open("docs/latest_changes.rst", "w") as f:
        f.write(changes)

    with cd("examples"):
       ctx.run("jupyter nbconvert --to html *.ipynb")
       ctx.run("mv *.html ../docs/_static")
    with cd("docs"):
        ctx.run("cp ../CHANGES.rst change_log.rst")
        ctx.run("sphinx-apidoc --separate -d 6 -o . -f ../pymatgen")
        ctx.run("rm pymatgen*.tests.*rst")
        for f in glob.glob("*.rst"):
            if f.startswith('pymatgen') and f.endswith('rst'):
                newoutput = []
                suboutput = []
                subpackage = False
                with open(f, 'r') as fid:
                    for line in fid:
                        clean = line.strip()
                        if clean == "Subpackages":
                            subpackage = True
                        if not subpackage and not clean.endswith("tests"):
                            newoutput.append(line)
                        else:
                            if not clean.endswith("tests"):
                                suboutput.append(line)
                            if clean.startswith("pymatgen") and not clean.endswith("tests"):
                                newoutput.extend(suboutput)
                                subpackage = False
                                suboutput = []

                with open(f, 'w') as fid:
                    fid.write("".join(newoutput))
        ctx.run("make html")
        ctx.run("cp _static/* _build/html/_static")

        # This makes sure pymatgen.org works to redirect to the Gihub page
        ctx.run("echo \"pymatgen.org\" > _build/html/CNAME")
        # Avoid ths use of jekyll so that _dir works as intended.
        ctx.run("touch _build/html/.nojekyll")


@task
def update_doc(ctx):
    with cd("docs/_build/html/"):
        ctx.run("git pull")
    make_doc(ctx)
    with cd("docs/_build/html/"):
        ctx.run("git add .")
        ctx.run("git commit -a -m \"Update dev docs\"")
        ctx.run("git push origin gh-pages")


@task
def publish(ctx):
    ctx.run("python setup.py release")


@task
def set_ver(ctx):
    lines = []
    with open("pymatgen/__init__.py", "rt") as f:
        for l in f:
            if "__version__" in l:
                lines.append('__version__ = "%s"' % NEW_VER)
            else:
                lines.append(l.rstrip())
    with open("pymatgen/__init__.py", "wt") as f:
        f.write("\n".join(lines))

    lines = []
    with open("setup.py", "rt") as f:
        for l in f:
            lines.append(re.sub(r'version=([^,]+),', 'version="%s",' % NEW_VER,
                                l.rstrip()))
    with open("setup.py", "wt") as f:
        f.write("\n".join(lines))


@task
def update_coverage(ctx):
    with cd("docs/_build/html/"):
        ctx.run("git pull")
    ctx.run("nosetests --config=nose.cfg --cover-html --cover-html-dir=docs/_build/html/coverage")
    update_doc()


@task
def merge_stable(ctx):
    ctx.run("git commit -a -m \"v%s release\"" % NEW_VER)
    ctx.run("git push")
    ctx.run("git checkout stable")
    ctx.run("git pull")
    ctx.run("git merge master")
    ctx.run("git push")
    ctx.run("git checkout master")


@task
def release_github(ctx):
    with open("CHANGES.rst") as f:
        contents = f.read()
    toks = re.split("\-+", contents)
    desc = toks[1].strip()
    toks = desc.split("\n")
    desc = "\n".join(toks[:-1]).strip()
    payload = {
        "tag_name": "v" + NEW_VER,
        "target_commitish": "master",
        "name": "v" + NEW_VER,
        "body": desc,
        "draft": False,
        "prerelease": False
    }
    response = requests.post(
        "https://api.github.com/repos/materialsproject/pymatgen/releases",
        data=json.dumps(payload),
        headers={"Authorization": "token " + os.environ["GITHUB_RELEASES_TOKEN"]})
    print(response.text)


@task
def update_changelog(ctx):

    output = subprocess.check_output(["git", "log", "--pretty=format:%s",
                                      "v%s..HEAD" % CURRENT_VER])
    lines = ["* " + l for l in output.decode("utf-8").strip().split("\n")]
    with open("CHANGES.rst") as f:
        contents = f.read()
    l = "=========="
    toks = contents.split(l)
    head = "\n\nv%s\n" % NEW_VER + "-" * (len(NEW_VER) + 1) + "\n"
    toks.insert(-1, head + "\n".join(lines))
    with open("CHANGES.rst", "w") as f:
        f.write(toks[0] + l + "".join(toks[1:]))


@task
def log_ver(ctx):
    filepath = os.path.join(os.environ["HOME"], "Dropbox", "Public",
                            "pymatgen", NEW_VER)
    with open(filepath, "w") as f:
        f.write("Release")


@task
def release(ctx, notest=False):
    set_ver(ctx)
    if not notest:
        ctx.run("nosetests")
    publish(ctx)
    log_ver(ctx)
    update_doc(ctx)
    merge_stable(ctx)
    release_github(ctx)


@task
def open_doc(ctx):
    pth = os.path.abspath("docs/_build/html/index.html")
    webbrowser.open("file://" + pth)
