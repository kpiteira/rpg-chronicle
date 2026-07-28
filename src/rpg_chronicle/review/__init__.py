"""The correction loop: what a person says back, and what it changes.

Deliberately empty of re-exports. `pipeline.py` imports `review.apply` to carry approved
names forward, and `review.session` imports `pipeline` to read and write a session
directory; a package that eagerly imported both would close that into a cycle. Import the
module you need.
"""
