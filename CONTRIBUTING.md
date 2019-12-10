# How to Contribute

## Follow the Decisions

`mvn2get.py` made a few design decisions that should be followed.

* It's a single file so that people can drop it anywhere without needing to run Pip or some other installation.  It's self-contained to make end-user usage a snap, at the expense of making it a bit more difficult to look at.
* It uses type annotations to stop bugs.
* The only use of external libraries are optional.
* Though `urllib3` would make things easier, it's explicitly not used because many of the Maven repositories actively refuse connections from it.


## Pre-Push Checklist



### Run the MyPy Linter

```bash
python -m mypy --warn-unused-configs --no-incremental mvn2get.py
```


### Run Unit Tests

```
python -m coverage run --source . -m unittest discover -s . -p "*_test.py"

# To view the generated coverage report
python -m coverage report -m
```
