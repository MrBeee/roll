"""use of nonumba.py is best done as follows
(This avoids using: from nonumba import *)

try:
    nb = importlib.import_module('numba')
except ImportError:
    nb = importlib.import_module('.nonumba', package='roll') # relative import requires package name

then, decorate functions with: @nb.jit(nopython=True)
"""

import functools

# See: https://stackoverflow.com/questions/3888158
# use numba decorators when numba package is not available


def optional_arg_decorator(fn):
    @functools.wraps(fn)
    def wrapped_decorator(*args, **kwargs):
        #        is_bound_method = hasattr(args[0], fn.__name__) if args else False

        #        if is_bound_method:
        #            klass = args[0]
        #            args = args[1:]

        # If no arguments were passed...
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            #            if is_bound_method:
            #                return fn(klass, args[0])
            #            else:
            return fn(args[0])

        else:

            def real_decorator(decoratee):
                #                if is_bound_method:
                #                    return fn(klass, decoratee, *args, **kwargs)
                #                else:
                return fn(decoratee, *args, **kwargs)

            return real_decorator

    return wrapped_decorator


@optional_arg_decorator
def __noop(func, *args, **kwargs):
    return func


autojit = __noop
generated_jit = __noop
guvectorize = __noop
jit = __noop
jitclass = __noop
njit = __noop
vectorize = __noop

b1 = None
bool_ = None
boolean = None
byte = None
c16 = None
c8 = None
char = None
complex128 = None
complex64 = None
double = None
f4 = None
f8 = None
ffi = None
ffi_forced_object = None
float32 = None
float64 = None
float_ = None
i1 = None
i2 = None
i4 = None
i8 = None
int16 = None
int32 = None
int64 = None
int8 = None
int_ = None
intc = None
intp = None
long_ = None
longlong = None
none = None
short = None
u1 = None
u2 = None
u4 = None
u8 = None
uchar = None
uint = None
uint16 = None
uint32 = None
uint64 = None
uint8 = None
uintc = None
uintp = None
ulong = None
ulonglong = None
ushort = None
void = None
