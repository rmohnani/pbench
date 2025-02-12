# Pbench
A Benchmarking and Performance Analysis Framework

The code base includes three sub-systems. The first is the collection agent,
`pbench-agent`, responsible for providing commands for running benchmarks
across one or more systems, while properly collecting the configuration data
for those systems, and specified telemetry or data from various tools (`sar`,
`vmstat`, `perf`, etc.).

The second sub-system is the `pbench-server`, which is responsible for
archiving result tar balls, indexing them, and unpacking them for display.

The third sub-system is the `web-server` JS and CSS files, used to display
various graphs and results, and any other content generated by the
`pbench-agent` during benchmark and tool post-processing steps.

The pbench Dashboard code lives in its own [repository](
https://github.com/distributed-system-analysis/pbench-dashboard).

## How is it installed?
Instructions on installing `pbench-agent`, can be found
in the Pbench Agent [Getting Started Guide](
https://distributed-system-analysis.github.io/pbench/start.html).

For Fedora, CentOS, and RHEL users, we have made available [COPR
builds](https://copr.fedorainfracloud.org/coprs/ndokos/pbench/) for the
`pbench-agent`, `pbench-server`, `pbench-web-server`, and some benchmark and
tool packages.

Install the `pbench-web-server` package on the machine from where you want to
run the `pbench-agent` workloads, allowing you to view the graphs before
sending the results to a server, or even if there is no server configured to
send results.

You might want to consider browsing through the [rest of the documentation](
https://distributed-system-analysis.github.io/pbench/doc.html).

## How do I use pbench?
Refer to the [Pbench Agent Getting Started Guide](
https://distributed-system-analysis.github.io/pbench/start.html).

TL;DR? See "[TL;DR - How to set up the `pbench-agent` and run a benchmark
](https://distributed-system-analysis.github.io/pbench/doc.html#how)" in the
main documentation for a super quick set of introductory steps.

## Where is the source kept?
The latest source code is at
https://github.com/distributed-system-analysis/pbench.

The pbench dashboard code is maintained separately at
https://github.com/distributed-system-analysis/pbench-dashboard.

## Is there a mailing list for discussions?

Yes, we use [Google Groups](https://groups.google.com/forum/#!forum/pbench)

## How do I report and issue?

Please use GitHub's [issues](
https://github.com/distributed-system-analysis/pbench/issues/new/choose).

## Is there a place to track current and future work items?

Yes, we are using GitHub [Projects](
https://github.com/distributed-system-analysis/pbench/projects).
Please find projects covering the [Agent](
https://github.com/distributed-system-analysis/pbench/projects/2),
[Server](https://github.com/distributed-system-analysis/pbench/projects/3),
[Dashboard]()https://github.com/distributed-system-analysis/pbench/projects/1,
and a project that is named the same as the current [milestone](
https://github.com/distributed-system-analysis/pbench/milestones).

## How can I contribute?

Below are some simple steps for setting up a development environment for
working with the Pbench code base.  For more detailed instructions on the
workflow and process of contributing code to Pbench, refer to the [Guidelines
for Contributing](doc/CONTRIBUTING.md).

### Getting the Code

```
$ git clone https://github.com/distributed-system-analysis/pbench
$ cd pbench
```

### Running the Unit Tests

Install `tox` properly in your environment (Fedora/CentOS/RHEL):

```
$ sudo dnf install -y perl-JSON python3-pip python3-tox
```

Once tox is installed you can run the unit tests against different versions of
python using the python environment short-hands:

  * `tox -e py36`    -- run all tests in a Python 3.6 environment (our default)
  * `tox -e py39`    -- run all tests in a Python 3.9 environment
  * `tox -e py310`   -- run all tests in a Python 3.10 environment
  * `tox -e pypy3`   -- run all tests in a PyPy 3 environment
  * `tox -e pypy3.8` -- run all tests in a PyPy 3.8 environment

See https://tox.wiki/en/latest/example/basic.html#a-simple-tox-ini-default-environments.

Each time tests are run, the linting steps (`black` and `flake8`) are run first.

You can provide arguments to the `tox` invocation to request sub-sets of the
available tests be run.

For example, if you want to just run the agent or server tests, you'd invoke
`tox` as follows:

  * `tox -- agent`   -- runs only the agent tests
  * `tox -- server`  -- runs only the server tests

Each of the "agent" and "server" tests can be further subsetted as follows:

  * agent
    * python          -- runs the python tests (via `pytest`)
    * legacy          -- runs all the legacy tests
    * datalog         -- runs only the legacy tool data-log tests,
                         `agent/tool-scripts/datalog/unittests`
    * postprocess     -- runs only the legacy tool/bench-scripts post-processing
                         tests, `agent/tool-scripts/postprocess/unittests`
    * tool-scripts    -- runs only the legacy tool-scripts tests,
                         `agent/tool-scripts/unittests`
    * util-scripts    -- runs only the legacy util-scripts tests,
                         `agent/util-scripts/unittests`
    * bench-scripts   -- runs only the legacy bench-scripts tests,
                         `agent/bench-scripts/unittests`

  * server
    * python          -- runs the python tests (via python)
    * legacy          -- runs the legacy tests

For example:

  * `tox -- agent legacy`   -- run agent legacy tests
  * `tox -- server legacy`  -- run server legacy tests
  * `tox -- server python`  -- run server python tests (via `pytest`)

For any of the test sub-sets on either the agent or server sides of the tree,
one can pass additional arguments to the specific sub-system test runner.  This
allows one to request a specific test, or set of tests, or command line
parameters to modify the test behavior:

  * `tox -- agent bench-scripts test-CL`    -- run bench-scripts' test-CL
  * `tox -- server legacy test-28 test-32`  -- run server legacy tests 28 & 32
  * `tox -- server python -v`               -- run server python tests verbosely

For the `agent/bench-scripts` tests, one can run entire sub-sets of tests using
a sub-directory name found in `agent/bench-scripts/tests`. For example:

  * `tox -- agent bench-scripts pbench-fio`
  * `tox -- agent bench-scripts pbench-uperf pbench-linpack`

The first runs all the `pbench-fio` tests, while the second runs all the
`pbench-uperf` and `pbench-linpack` tests.

Finally, see the `jenkins/Pipeline.gy` file for how the unit tests are run in
our CI jobs.

### Python formatting

This project uses the [flake8==3.8.3](http://flake8.pycqa.org/en/latest) method of
code style enforcement, linting, and checking.

All python code contributed to pbench must match the style requirements. These
requirements are enforced by the [pre-commit](https://pre-commit.com) hook
using the [black==1.19b0](https://github.com/psf/black) Python code formatter.

### Use pre-commit to set automatic commit requirements

This project makes use of [pre-commit](https://pre-commit.com/) to do automatic
lint and style checking on every commit containing Python files.

To install the pre-commit hook, run the executable from your Python 3 framework
while in your current pbench git checkout:

```
$ cd ~/pbench
$ pip3 install pre-commit
$ pre-commit install --install-hooks
```

Once installed, all commits will run the test hooks. If your changes fail any of
the tests, the commit will be rejected.

## Pbench Release Tag Scheme (GitHub)
We employ a simple major, minor, release, build (optional) scheme for tagging
starting with the `v0.70.0` release (`v<Major>.<Minor>.<Release>[-<Build>]`).
Prior to the v0.70.0 release, the scheme used was mostly `v<Major>.<Minor>`,
where we only had minor releases (`Major = 0`).

The practice of using `-agent` or `-server` is also ending with the `v0.70.0`
release.

### Container Image Tags
This same GitHub "tag" scheme is used with tags applied to container images
we build, with the following exceptions for tag names:

  * `latest` - always points to the "latest" container image pushed to a
    repository

  * `v<Major>-latest` - always points to the "latest" `Major` released
    image

  * `v<Major>.<Minor>-latest` - always points to the "latest" release
    for `Major`.`Minor` released images

  * `<SHA1 git hash>` (9 characters) - commit hash of the checked out code
