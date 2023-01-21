import inspect
import operator
import typing

from beartype.door import TypeHint, is_bearable
from beartype.peps import resolve_pep563

from .type import is_faithful, resolve_type_hint
from .util import Comparable, Missing, multihash, wrap_lambda

__all__ = ["Signature", "extract_signature", "append_default_args"]


class Signature(Comparable):
    """Signature.

    Args:
        *types (tuple[type, ...]): Types of the arguments.
        varargs (type, optional): Type of the variable arguments.
        return_type (type, optional): Type of the return value. Defaults to `Any`.
        precedence (int, optional): Precedence. Default to `0`.
        implementation (function, optional): Implementation.

    Attributes:
        types (tuple[type, ...]): Types of the arguments.
        varargs (type or :class:`.util.Missing`): Type of the variable number of
            arguments.
        has_varargs (bool): Whether `varargs` is not :class:`.util.Missing`.
        return_type (type): Return type.
        precedence (int): Precedence.
        implementation (function or None): Implementation.
        is_faithful (bool): Whether this signature only uses faithful types.
    """

    def __init__(
        self,
        *types,
        varargs=Missing,
        return_type=typing.Any,
        precedence=0,
        implementation=None,
    ):
        self.types = types
        self.varargs = varargs
        self.return_type = return_type
        self.precedence = precedence
        self.implementation = implementation

        types_are_faithful = all(is_faithful(t) for t in types)
        varargs_are_faithful = self.varargs is Missing or is_faithful(self.varargs)
        self.is_faithful = types_are_faithful and varargs_are_faithful

    @property
    def has_varargs(self):
        return self.varargs is not Missing

    def __copy__(self):
        return Signature(
            *self.types,
            varargs=self.varargs,
            return_type=self.return_type,
            precedence=self.precedence,
            implementation=self.implementation,
        )

    def __repr__(self):
        types_repr = ", ".join(map(repr, self.types))
        if types_repr:
            types_repr += ", "
        return (
            f"Signature("
            f"{types_repr}"
            f"varargs={self.varargs!r}, "
            f"return_type={self.return_type!r})"
        )

    def __hash__(self):
        return multihash(Signature, *self.types, self.varargs)

    def expand_varargs(self, n):
        """Expand variable arguments.

        Args:
            n (int): Desired number of types.

        Returns:
            tuple[type, ...]: Expanded types.
        """
        if self.has_varargs:
            expansion_size = max(n - len(self.types), 0)
            return self.types + (self.varargs,) * expansion_size
        else:
            return self.types

    def __le__(self, other):
        # If this signature has variable arguments, but the other does not, then this
        # signature cannot be possibly smaller.
        if self.has_varargs and not other.has_varargs:
            return False

        # If this signature and the other signature both have variable arguments, then
        # the variable type of this signature must be less than the variable type of the
        # other signature.
        if (
            self.has_varargs
            and other.has_varargs
            and not (TypeHint(self.varargs) <= TypeHint(other.varargs))
        ):
            return False

        # If the number of types of the signatures are unequal, then the signature
        # with the fewer number of types must be expanded using variable arguments.
        if not (
            len(self.types) == len(other.types)
            or (len(self.types) > len(other.types) and other.has_varargs)
            or (len(self.types) < len(other.types) and self.has_varargs)
        ):
            return False

        # Finally, expand the types and compare.
        self_types = self.expand_varargs(len(other.types))
        other_types = other.expand_varargs(len(self.types))
        return all(
            [TypeHint(x) <= TypeHint(y) for x, y in zip(self_types, other_types)]
        )

    def match(self, values):
        """Check whether values match the signature.

        Args:
            values (tuple): Values.

        Returns:
            bool: `True` if `values` match this signature and `False` otherwise.
        """
        # `values` must either be exactly many as `self.types`. If there are more
        # `values`, then there must be variable arguments to cover the arguments.
        if not (
            len(self.types) == len(values)
            or (len(self.types) < len(values) and self.has_varargs)
        ):
            return False
        else:
            types = self.expand_varargs(len(values))
            return all(is_bearable(v, t) for v, t in zip(values, types))


def _is_not_empty(t):
    """Check if a type is *not* equal to `inspect.Parameter.empty`, without triggering
    unwanted `__eq__`-like methods.

    Args:
        t (type): Type to check.

    Returns:
        bool: `True` if `t` is *not* `inspect.Parameter.empty`.
    """
    return t is not inspect.Parameter.empty


def _inspect_signature(f):
    """Wrapper of :func:`inspect.signature` which adds support for certain non-function
    objects.

    Args:
        f (object): Function-like object.

    Returns:
        object: Signature.
    """
    if isinstance(f, operator.itemgetter):
        f = wrap_lambda(f)
    elif isinstance(f, operator.attrgetter):
        f = wrap_lambda(f)
    return inspect.signature(f)


def extract_signature(f, precedence=0):
    """Extract the signature from a function.

    Args:
        f (function): Function to extract signature from.
        precedence (int, optional): Precedence of the method.

    Returns:
        :class:`.Signature`: Signature.
    """
    if hasattr(f, "__annotations__"):
        resolve_pep563(f)  # This mutates `f`.
        # Override the `__annotations__` attribute, since `resolve_pep563` modifies
        # `f` too.
        for k, v in typing.get_type_hints(f).items():
            f.__annotations__[k] = v

    # Extract specification.
    sig = _inspect_signature(f)

    # Get types of arguments.
    types = []
    varargs = Missing
    for arg in sig.parameters:
        p = sig.parameters[arg]

        # Parse and resolve annotation.
        if _is_not_empty(p.annotation):
            annotation = resolve_type_hint(p.annotation)
        else:
            annotation = typing.Any

        # Stop once we have seen all positional parameter without a default value.
        if p.kind in {p.KEYWORD_ONLY, p.VAR_KEYWORD}:
            break

        if p.kind == p.VAR_POSITIONAL:
            # Parameter indicates variable arguments.
            varargs = annotation
        else:
            # Parameter is a regular positional parameter.
            types.append(annotation)

        # If there is a default parameter, make sure that it is of the annotated type.
        if _is_not_empty(p.default):
            if not is_bearable(p.default, annotation):
                raise TypeError(
                    f"Default value `{p.default}` is not an instance "
                    f"of the annotated type `{annotation}`."
                )

    # Get possible return type.
    if _is_not_empty(sig.return_annotation):
        return_type = resolve_type_hint(sig.return_annotation)
    else:
        return_type = typing.Any

    # Assemble signature.
    signature = Signature(
        *types,
        varargs=varargs,
        return_type=return_type,
        precedence=precedence,
        implementation=f,
    )

    return signature


def append_default_args(signature, f):
    """Returns a list of signatures of function `f`, where those signatures are derived
    from the input arguments of `f` by treating every non-keyword-only argument with a
    default value as a keyword-only argument turn by turn.

    Args:
        f (function): Function to extract default arguments from.
        signature (:class:`.signature.Signature`): Signature of `f` from which to
            remove default arguments.

    Returns:
        list[:class:`.signature.Signature`]: list of signatures excluding from 0 to all
        default arguments.
    """
    # Extract specification.
    f_signature = _inspect_signature(f)

    signatures = [signature]

    arg_names = list(f_signature.parameters.keys())
    # We start at the end and, once we reach non-keyword-only arguments, delete the
    # argument with defaults values one by one. This generates a sequence of signatures,
    # which we return.
    arg_names.reverse()

    for arg in arg_names:
        p = f_signature.parameters[arg]

        # Ignore variable arguments and keyword arguments.
        if p.kind in {p.VAR_KEYWORD, p.KEYWORD_ONLY}:
            continue

        # Stop when non-variable arguments without a default are reached.
        if p.kind != p.VAR_POSITIONAL and not _is_not_empty(p.default):
            break

        # Skip variable arguments. These will always be removed.
        if p.kind == p.VAR_POSITIONAL:
            continue

        copy = signatures[-1].__copy__()

        # As specified over, these additional signatures should never have variable
        # arguments.
        copy.varargs = Missing

        # Remove the last positional argument.
        copy.types = copy.types[:-1]

        signatures.append(copy)

    return signatures
