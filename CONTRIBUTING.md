# How to Contribute

## Use the Right Branch

New development work happens in the `dev` branch.

## Follow the Decisions

`mvn2get.py` made a few design decisions that should be followed.

* It's a single file so that people can drop it anywhere without needing to run Pip or some other installation.  It's self-contained to make end-user usage a snap, at the expense of making it a bit more difficult to look at.
* It uses type annotations to stop bugs.
* The only use of external libraries are optional.
* Though `urllib3` would make things easier, it's explicitly not used because many of the Maven repositories actively refuse connections from it.


## Pre-Push Checklist

### Copyright Update

Make sure the copyright information and date in the [program](mvn2get.py) and the [license file](LICENSE) are up-to-date.

### Version Update

Make sure the version number in the [program](mvn2get.py) and the [README.md]() file are updated.  Include the changes in the [changelog](CHANGELOG.md).

### Run MyPy

Make sure mypy reports no errors.

```bash
python -m mypy --warn-unused-configs --no-incremental mvn2get.py
```


### Run Unit Tests

Make sure the unit tests pass with no errors.  Additionally, coverage must not go down.

```bash
python -m coverage run --source . -m unittest discover -s . -p "*_test.py"

# To view the generated coverage report
python -m coverage report -m mvn2get.py
```

Previous release coverage:

Statements: 1197
Miss: 877
Coverage: 27%
