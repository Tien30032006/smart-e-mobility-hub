"""Marker for unimplemented work.

Every stub in the project calls ``todo(owner, use_case, hint)``. Over HTTP this
becomes a 501 response that names the owner and the use case, so anyone who
hits an unfinished endpoint knows exactly who is responsible.
Delete the ``todo(...)`` call when you implement the function.
"""


class NotImplementedYet(NotImplementedError):
    def __init__(self, owner: str, use_case: str, hint: str = ""):
        self.owner = owner
        self.use_case = use_case
        self.hint = hint
        super().__init__(f"TODO [{owner}] {use_case}: {hint}".strip())


def todo(owner: str, use_case: str, hint: str = ""):
    raise NotImplementedYet(owner, use_case, hint)
